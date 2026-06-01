from __future__ import annotations

import logging
import re
import threading
import time
from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from backend.database import session_scope
from backend.models import AppSetting
from backend.noren import NorenError, get_noren_rates, rate_pair_key
from backend.payment_settings import normalize_payment_settings

logger = logging.getLogger(__name__)

_lock = threading.RLock()
_min_deposits: dict[str, Decimal] = {}
_updated_at: float = 0.0


def _parse_limit(raw) -> Decimal | None:
    if raw is None:
        return None
    try:
        value = Decimal(str(raw).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if value <= 0:
        return None
    return value


def _first_noren_config() -> dict | None:
    with session_scope() as session:
        rows = session.scalars(select(AppSetting).where(AppSetting.key == "payment"))
        for row in rows:
            payment = normalize_payment_settings(row.value)
            noren = payment["noren"]
            if noren.get("api_key") and noren.get("api_secret"):
                return noren
    return None


def refresh_noren_deposit_limits() -> int:
    global _updated_at
    noren = _first_noren_config()
    if noren is None:
        return 0
    try:
        rates = get_noren_rates(noren=noren)
    except NorenError as exc:
        logger.warning("Noren deposit limits refresh failed: %s", exc)
        return 0
    found: dict[str, Decimal] = {}
    for rate in rates:
        min_dep = _parse_limit(rate.get("min_deposit"))
        if min_dep is None:
            continue
        key = rate_pair_key(rate["currency"], rate["network"])
        found[key] = min_dep
    with _lock:
        _min_deposits.clear()
        _min_deposits.update(found)
        _updated_at = time.time()
    logger.info("Noren deposit limits refreshed: %s pairs", len(found))
    return len(found)


def get_min_deposit(*, currency: str, network: str) -> Decimal | None:
    key = rate_pair_key(currency, network)
    with _lock:
        return _min_deposits.get(key)


_MIN_LIMIT_RE = re.compile(
    r"minimum limit\s+(?P<min>[\d.]+)\s+(?P<currency>[A-Z0-9]+)",
    re.IGNORECASE,
)
_AMOUNT_RE = re.compile(
    r"Amount\s+(?P<amount>[\d.]+)\s+(?P<currency>[A-Z0-9]+)",
    re.IGNORECASE,
)


def humanize_provider_error(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return "Ошибка провайдера оплаты."
    if "1143" in text or "minimum limit" in text.lower():
        min_match = _MIN_LIMIT_RE.search(text)
        amount_match = _AMOUNT_RE.search(text)
        if min_match:
            minimum = min_match.group("min")
            currency = min_match.group("currency").upper()
            amount_part = ""
            if amount_match:
                amount_part = f" (запрошено {amount_match.group('amount')} {amount_match.group('currency').upper()})"
            return (
                f"Сумма{amount_part} меньше минимума провайдера: минимум <b>{minimum} {currency}</b>.\n"
                f"Увеличьте цену Noren в админке или выберите другую монету (например USDT)."
            )
    if len(text) > 400:
        return text[:400] + "…"
    return text


def checkout_minimum_error(
    *,
    usd_amount: str,
    currency: str,
    network: str,
    crypto_amount: Decimal,
) -> str | None:
    min_dep = get_min_deposit(currency=currency, network=network)
    if min_dep is None or crypto_amount >= min_dep:
        return None
    sym = str(currency or "").strip().upper()
    net = str(network or "").strip().upper()
    return (
        f"Сумма <b>{usd_amount} USD</b> (≈ {crypto_amount} {sym}) меньше минимума "
        f"<b>{min_dep} {sym}</b> для {sym} · {net}.\n"
        f"Увеличьте цену Noren в админке или выберите USDT."
    )
