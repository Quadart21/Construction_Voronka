from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from backend.config import settings
from backend.payment_settings import normalize_payment_settings


class NorenError(RuntimeError):
    pass


NOREN_STATUS_EVENTS = frozenset({"invoice.paid", "invoice.confirmed"})


def crypto_provider_name() -> str:
    provider = str(settings.payment_provider or "").strip().lower()
    return provider if provider else "noren"


def _headers(noren: dict) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-API-Key": noren["api_key"],
        "X-API-Secret": noren["api_secret"],
    }


def flatten_rates(items: list[dict] | None) -> list[dict]:
    result: list[dict] = []
    for item in items or []:
        currency = str(item.get("currency") or "").strip().upper()
        if not currency:
            continue
        for network in item.get("networks") or []:
            if not isinstance(network, dict):
                continue
            network_code = str(network.get("network") or "").strip().upper()
            if not network_code:
                continue
            available = bool(network.get("client_available", True)) and bool(network.get("acquiring", True))
            result.append(
                {
                    "currency": currency,
                    "network": network_code,
                    "label": f"{currency} ({network_code})",
                    "ticker": network.get("ticker"),
                    "min_deposit": network.get("min_deposit"),
                    "max_deposit": network.get("max_deposit"),
                    "available": available,
                }
            )
    return result


def get_noren_rates(*, noren: dict) -> list[dict]:
    cfg = normalize_payment_settings({"noren": noren})["noren"]
    if not cfg["api_key"] or not cfg["api_secret"]:
        raise NorenError("Укажите API key и secret Noren в настройках")
    response = requests.get(f"{cfg['base_url']}/rates", headers=_headers(cfg), timeout=20)
    response.raise_for_status()
    payload = response.json()
    items = payload.get("items") if isinstance(payload, dict) else payload
    return flatten_rates(items)


def _parse_amount(value: str) -> str:
    raw = str(value or "").strip().replace(",", ".")
    if not raw:
        raise NorenError("Укажите сумму оплаты Noren в выбранной криптовалюте")
    try:
        amount = Decimal(raw)
    except InvalidOperation as exc:
        raise NorenError("Сумма Noren должна быть числом") from exc
    if amount <= 0:
        raise NorenError("Сумма Noren должна быть больше нуля")
    normalized = format(amount.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def create_noren_invoice(
    *,
    noren: dict,
    merchant_order_id: str,
    metadata: dict | None = None,
) -> dict[str, Any]:
    cfg = normalize_payment_settings({"noren": noren})["noren"]
    if not cfg["api_key"] or not cfg["api_secret"] or not cfg["project_id"]:
        raise NorenError("Noren: заполните API key, secret и project_id")
    amount = _parse_amount(cfg["amount"])
    body = {
        "project_id": cfg["project_id"],
        "merchant_order_id": merchant_order_id,
        "amount_fiat": amount,
        "fiat_currency": cfg["crypto_currency"],
        "crypto_currency": cfg["crypto_currency"],
        "network": cfg["network"],
        "metadata": metadata or {},
    }
    response = requests.post(f"{cfg['base_url']}/invoices", headers=_headers(cfg), json=body, timeout=25)
    if response.status_code >= 400:
        detail = response.text[:500]
        raise NorenError(f"Noren API error {response.status_code}: {detail}")
    return response.json()


def new_merchant_order_id() -> str:
    return f"order-{uuid.uuid4().hex[:12]}"


def extract_invoice_details(invoice: dict[str, Any]) -> dict[str, str]:
    merchant_order_id = str(invoice.get("merchant_order_id") or "").strip()
    amount_crypto = str(invoice.get("amount_crypto") or "").strip()
    crypto_currency = str(invoice.get("crypto_currency") or "").strip().upper()
    network = str(invoice.get("network") or "").strip().upper()
    payment_address = str(invoice.get("payment_address") or "").strip()
    qr_url = str(invoice.get("qr_url") or "").strip()
    expires_at = str(invoice.get("expires_at") or "").strip()
    invoice_id = str(invoice.get("id") or "").strip()
    missing = [
        name
        for name, value in {
            "merchant_order_id": merchant_order_id,
            "amount_crypto": amount_crypto,
            "crypto_currency": crypto_currency,
            "network": network,
            "payment_address": payment_address,
        }.items()
        if not value
    ]
    if missing:
        raise NorenError(f"Noren не вернул реквизиты: {', '.join(missing)}")
    return {
        "invoice_id": invoice_id,
        "merchant_order_id": merchant_order_id,
        "amount_crypto": amount_crypto,
        "crypto_currency": crypto_currency,
        "network": network,
        "payment_address": payment_address,
        "qr_url": qr_url,
        "expires_at": expires_at,
        "expires_label": format_expires_at_utc(expires_at),
    }


def format_expires_at_utc(raw: str | None) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return f"до {dt.strftime('%H:%M')} UTC"
    except ValueError:
        return f"до {value}"


def format_noren_payment_text(details: dict[str, str]) -> tuple[str, str]:
    title = f"Оплата заказа {details['merchant_order_id']}"
    lines = [
        f"{details['amount_crypto']} {details['crypto_currency']} · {details['network']}",
        f"Адрес: {details['payment_address']}",
    ]
    if details.get("expires_label"):
        lines.append(f"Срок: {details['expires_label']}")
    return title, "\n".join(lines)


def verify_noren_webhook_signature(*, secret: str, raw_body: bytes, signature: str | None) -> bool:
    if not secret:
        return True
    if not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = signature.strip()
    if provided.startswith("sha256="):
        provided = provided.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


NOREN_STATUS_MAP = {
    "CONFIRMED": "paid",
    "PAID": "paid",
    "COMPLETED": "paid",
    "SUCCESS": "paid",
    "PENDING": "pending",
    "AWAITING": "pending",
    "CREATED": "pending",
    "EXPIRED": "failed",
    "FAILED": "failed",
    "CANCELLED": "failed",
    "CANCELED": "failed",
}


def map_noren_status(raw: str | None) -> str:
    key = str(raw or "").strip().upper()
    if key in NOREN_STATUS_MAP:
        return NOREN_STATUS_MAP[key]
    lowered = str(raw or "").strip().lower()
    if lowered in {"confirmed", "paid", "completed"}:
        return "paid"
    if lowered in {"expired", "failed", "cancelled", "canceled"}:
        return "failed"
    return lowered or "unknown"
