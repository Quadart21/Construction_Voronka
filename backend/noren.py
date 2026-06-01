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
            client_ok = bool(network.get("client_available", True))
            acquiring = bool(network.get("acquiring", True))
            platform_ok = bool(network.get("platform_enabled", True))
            provider_ok = bool(network.get("provider_availability", True))
            available = client_ok and acquiring and platform_ok and provider_ok
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


def get_available_rates(*, noren: dict) -> list[dict]:
    return [item for item in get_noren_rates(noren=noren) if item.get("available", True)]


def rate_pair_key(currency: str, network: str) -> str:
    return f"{str(currency or '').strip().upper()}|{str(network or '').strip().upper()}"


def get_admin_allowed_rates(*, noren: dict) -> list[dict]:
    cfg = normalize_payment_settings({"noren": noren})["noren"]
    allowed_keys = set(cfg.get("allowed_cryptos") or [])
    if not allowed_keys:
        return []
    return [
        rate
        for rate in get_available_rates(noren=noren)
        if rate_pair_key(rate["currency"], rate["network"]) in allowed_keys
    ]


def is_allowed_crypto(*, noren: dict, crypto_currency: str, network: str) -> bool:
    cfg = normalize_payment_settings({"noren": noren})["noren"]
    key = rate_pair_key(crypto_currency, network)
    return key in set(cfg.get("allowed_cryptos") or [])


def get_noren_rates(*, noren: dict) -> list[dict]:
    cfg = normalize_payment_settings({"noren": noren})["noren"]
    if not cfg["api_key"] or not cfg["api_secret"]:
        raise NorenError("Укажите API key и secret Noren в настройках")
    try:
        response = requests.get(f"{cfg['base_url']}/rates", headers=_headers(cfg), timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise NorenError(f"Не удалось получить курсы Noren: {exc}") from exc
    payload = response.json()
    items = payload.get("items") if isinstance(payload, dict) else payload
    return flatten_rates(items)


def _parse_amount(value: str | int | float) -> str:
    if isinstance(value, (int, float)):
        raw = str(value)
    else:
        raw = str(value or "").strip().replace(",", ".")
    if not raw:
        raise NorenError("Укажите сумму оплаты")
    try:
        amount = Decimal(raw)
    except InvalidOperation as exc:
        raise NorenError("Сумма оплаты должна быть числом") from exc
    if amount <= 0:
        raise NorenError("Сумма оплаты должна быть больше нуля")
    normalized = format(amount.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


NOREN_INVOICE_FIAT = "USD"


def noren_checkout_fiat(noren: dict) -> tuple[str, str]:
    cfg = normalize_payment_settings({"noren": noren})["noren"]
    price_raw = str(cfg.get("price") or cfg.get("amount") or "").strip()
    if not price_raw:
        raise NorenError("Укажите цену крипто-оплаты в админке → Способы оплаты → Noren")
    price_currency = str(cfg.get("price_currency") or "USD").strip().upper()
    try:
        price = Decimal(_parse_amount(price_raw))
    except NorenError as exc:
        raise NorenError("Цена крипто-оплаты должна быть положительным числом") from exc
    if price_currency == "USD":
        usd_amount = price
    elif price_currency == "RUB":
        rate_raw = str(cfg.get("usd_rub_rate") or "").strip()
        if not rate_raw:
            raise NorenError("Укажите курс «RUB за 1 USD» для конвертации цены из рублей")
        try:
            rate = Decimal(_parse_amount(rate_raw))
        except NorenError as exc:
            raise NorenError("Курс USD/RUB должен быть положительным числом") from exc
        usd_amount = price / rate
    else:
        raise NorenError("Цена крипто-оплаты: только USD или RUB")
    return _parse_amount(usd_amount), NOREN_INVOICE_FIAT


def noren_price_label(noren: dict) -> str:
    cfg = normalize_payment_settings({"noren": noren})["noren"]
    amount_usd, _ = noren_checkout_fiat(noren)
    price_raw = str(cfg.get("price") or cfg.get("amount") or "").strip()
    price_currency = str(cfg.get("price_currency") or "USD").strip().upper()
    if price_currency == "RUB":
        return f"{price_raw} RUB (≈ {amount_usd} USD)"
    return f"{amount_usd} USD"


def create_noren_invoice(
    *,
    noren: dict,
    merchant_order_id: str,
    crypto_currency: str,
    network: str,
    amount_fiat: str,
    fiat_currency: str,
    metadata: dict | None = None,
) -> dict[str, Any]:
    cfg = normalize_payment_settings({"noren": noren})["noren"]
    if not cfg["api_key"] or not cfg["api_secret"] or not cfg["project_id"]:
        raise NorenError("Noren: заполните API key, secret и project_id")
    currency = str(crypto_currency or "").strip().upper()
    network_code = str(network or "").strip().upper()
    if not currency or not network_code:
        raise NorenError("Выберите криптовалюту и сеть")
    body = {
        "project_id": cfg["project_id"],
        "merchant_order_id": merchant_order_id,
        "amount_fiat": _parse_amount(amount_fiat),
        "fiat_currency": NOREN_INVOICE_FIAT,
        "crypto_currency": currency,
        "network": network_code,
        "metadata": metadata or {},
    }
    try:
        response = requests.post(f"{cfg['base_url']}/invoices", headers=_headers(cfg), json=body, timeout=25)
    except requests.RequestException as exc:
        raise NorenError(f"Не удалось создать счёт Noren: {exc}") from exc
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
    payment_page_url = str(invoice.get("payment_page_url") or "").strip()
    amount_fiat = str(invoice.get("amount_fiat") or "").strip()
    fiat_currency = str(invoice.get("fiat_currency") or "").strip().upper()
    expires_at = str(invoice.get("expires_at") or "").strip()
    invoice_id = str(invoice.get("id") or "").strip()
    missing = [
        name
        for name, value in {
            "merchant_order_id": merchant_order_id,
            "amount_crypto": amount_crypto,
            "crypto_currency": crypto_currency,
            "network": network,
        }.items()
        if not value
    ]
    if missing:
        raise NorenError(f"Noren не вернул реквизиты: {', '.join(missing)}")
    if not payment_address and not payment_page_url and not qr_url:
        raise NorenError("Noren не вернул ссылку или адрес для оплаты")
    return {
        "invoice_id": invoice_id,
        "merchant_order_id": merchant_order_id,
        "amount_crypto": amount_crypto,
        "crypto_currency": crypto_currency,
        "network": network,
        "payment_address": payment_address,
        "qr_url": qr_url,
        "payment_page_url": payment_page_url,
        "amount_fiat": amount_fiat,
        "fiat_currency": fiat_currency,
        "expires_at": expires_at,
        "expires_label": format_expires_at_utc(expires_at),
    }


def invoice_payment_url(details: dict[str, str]) -> str:
    for key in ("payment_page_url", "qr_url"):
        value = str(details.get(key) or "").strip()
        if value.startswith(("http://", "https://")):
            return value
    return ""


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
    lines = [f"{details['amount_crypto']} {details['crypto_currency']} · {details['network']}"]
    if details.get("amount_fiat") and details.get("fiat_currency"):
        lines.append(f"≈ {details['amount_fiat']} {details['fiat_currency']}")
    if details.get("payment_address"):
        lines.append(f"Адрес: {details['payment_address']}")
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
