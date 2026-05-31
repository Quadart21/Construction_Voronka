from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from backend.models import PaymentRecord, User
from backend.noren import format_expires_at_utc

CRYPTO_PROVIDERS = ("noren", "crypto_cash")


def _utcnow() -> datetime:
    return datetime.utcnow()


def parse_expires_at(raw: str | None) -> datetime | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None


def invoice_is_active(record: PaymentRecord) -> bool:
    if record.status not in {"pending", "unknown", "awaiting", "created"}:
        return False
    expires_at = parse_expires_at((record.payload or {}).get("expires_at"))
    if expires_at is None:
        return True
    return expires_at > _utcnow()


def details_from_payment_record(record: PaymentRecord) -> dict[str, str]:
    payload = record.payload or {}
    expires_at = str(payload.get("expires_at") or "").strip()
    merchant_order_id = str(payload.get("merchant_order_id") or record.transaction_id or "").strip()
    amount_crypto = str(payload.get("amount_crypto") or "").strip()
    crypto_currency = str(payload.get("crypto_currency") or record.currency or "").strip().upper()
    network = str(payload.get("network") or "").strip().upper()
    payment_address = str(payload.get("payment_address") or "").strip()
    qr_url = str(payload.get("qr_url") or "").strip()
    if not all([merchant_order_id, amount_crypto, crypto_currency, network, payment_address]):
        raise ValueError("Incomplete stored invoice")
    return {
        "invoice_id": str(payload.get("invoice_id") or "").strip(),
        "merchant_order_id": merchant_order_id,
        "amount_crypto": amount_crypto,
        "crypto_currency": crypto_currency,
        "network": network,
        "payment_address": payment_address,
        "qr_url": qr_url,
        "expires_at": expires_at,
        "expires_label": format_expires_at_utc(expires_at),
    }


def get_active_crypto_invoice(session, *, bot_id: int, user_id: int) -> PaymentRecord | None:
    records = session.scalars(
        select(PaymentRecord)
        .where(
            PaymentRecord.bot_id == bot_id,
            PaymentRecord.user_id == user_id,
            PaymentRecord.provider.in_(CRYPTO_PROVIDERS),
            PaymentRecord.status == "pending",
        )
        .order_by(PaymentRecord.created_at.desc())
    )
    for record in records:
        if invoice_is_active(record):
            return record
    return None


def get_last_crypto_invoice(session, *, bot_id: int, user_id: int) -> PaymentRecord | None:
    return session.scalar(
        select(PaymentRecord)
        .where(
            PaymentRecord.bot_id == bot_id,
            PaymentRecord.user_id == user_id,
            PaymentRecord.provider.in_(CRYPTO_PROVIDERS),
        )
        .order_by(PaymentRecord.created_at.desc())
        .limit(1)
    )


def count_crypto_invoices_since(session, *, bot_id: int, user_id: int, since: datetime) -> int:
    return (
        session.scalar(
            select(func.count(PaymentRecord.id)).where(
                PaymentRecord.bot_id == bot_id,
                PaymentRecord.user_id == user_id,
                PaymentRecord.provider.in_(CRYPTO_PROVIDERS),
                PaymentRecord.created_at >= since,
            )
        )
        or 0
    )


def normalize_invoice_limits(noren: dict) -> dict:
    reuse_raw = noren.get("invoice_reuse_active")
    return {
        "invoice_reuse_active": reuse_raw is not False,
        "invoice_max_per_hour": max(1, int(noren.get("invoice_max_per_hour") or 3)),
        "invoice_cooldown_minutes": max(0, int(noren.get("invoice_cooldown_minutes") or 5)),
    }


class InvoiceCreationDecision:
    __slots__ = ("action", "record", "message")

    def __init__(self, action: str, record: PaymentRecord | None = None, message: str = ""):
        self.action = action
        self.record = record
        self.message = message


def check_crypto_invoice_creation(
    session,
    *,
    user: User,
    bot_id: int,
    limits: dict,
) -> InvoiceCreationDecision:
    cfg = normalize_invoice_limits(limits)
    active = get_active_crypto_invoice(session, bot_id=bot_id, user_id=user.id)
    if cfg["invoice_reuse_active"] and active is not None:
        return InvoiceCreationDecision("reuse", active)

    now = _utcnow()
    hour_ago = now - timedelta(hours=1)
    created_last_hour = count_crypto_invoices_since(session, bot_id=bot_id, user_id=user.id, since=hour_ago)
    if created_last_hour >= cfg["invoice_max_per_hour"]:
        return InvoiceCreationDecision(
            "blocked",
            message=(
                f"Слишком много заявок на оплату за последний час (лимит {cfg['invoice_max_per_hour']}). "
                "Подождите и попробуйте снова."
            ),
        )

    if cfg["invoice_cooldown_minutes"] > 0:
        last = get_last_crypto_invoice(session, bot_id=bot_id, user_id=user.id)
        if last is not None and last.created_at is not None:
            last_created = last.created_at.replace(tzinfo=None) if last.created_at.tzinfo else last.created_at
            elapsed = now - last_created
            cooldown = timedelta(minutes=cfg["invoice_cooldown_minutes"])
            if elapsed < cooldown:
                wait_minutes = max(1, int((cooldown - elapsed).total_seconds() // 60) or 1)
                return InvoiceCreationDecision(
                    "blocked",
                    message=f"Новую заявку можно создать через {wait_minutes} мин.",
                )

    return InvoiceCreationDecision("create")
