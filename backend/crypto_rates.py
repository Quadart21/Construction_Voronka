from __future__ import annotations

import asyncio
import logging
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Iterable

import requests
from sqlalchemy import select

from backend.database import session_scope
from backend.models import AppSetting
from backend.payment_settings import normalize_payment_settings

logger = logging.getLogger(__name__)

COINLORE_BASE = "https://api.coinlore.net/api"
REFRESH_INTERVAL_SECONDS = 300
REQUEST_GAP_SECONDS = 1.05
MAX_TICKER_PAGES = 20
TICKER_PAGE_SIZE = 100

STABLECOINS = frozenset({"USDT", "USDC", "BUSD", "DAI", "TUSD", "USDD", "FDUSD", "USDP", "PYUSD"})

_lock = threading.RLock()
_prices_usd: dict[str, Decimal] = {}
_updated_at: float = 0.0
_asset_ids: dict[str, str] = {}
_assets_loaded_at: float = 0.0


class CryptoRatesError(RuntimeError):
    pass


def _sleep_between_requests() -> None:
    time.sleep(REQUEST_GAP_SECONDS)


def _parse_price(raw) -> Decimal | None:
    try:
        price = Decimal(str(raw).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if price <= 0:
        return None
    return price


def _format_crypto_amount(amount: Decimal, symbol: str) -> str:
    sym = symbol.upper()
    if sym in STABLECOINS:
        quantized = amount.quantize(Decimal("0.000001"))
    else:
        quantized = amount.quantize(Decimal("0.00000001"))
    normalized = format(quantized.normalize(), "f")
    return normalized.rstrip("0").rstrip(".") if "." in normalized else normalized


def collect_tracked_symbols() -> set[str]:
    symbols = set(STABLECOINS)
    with session_scope() as session:
        rows = session.scalars(select(AppSetting).where(AppSetting.key == "payment"))
        for row in rows:
            payment = normalize_payment_settings(row.value)
            for key in payment["noren"].get("allowed_cryptos") or []:
                if isinstance(key, str) and "|" in key:
                    currency = key.split("|", 1)[0].strip().upper()
                    if currency:
                        symbols.add(currency)
    return symbols


def _load_asset_ids() -> dict[str, str]:
    global _asset_ids, _assets_loaded_at
    now = time.time()
    if _asset_ids and now - _assets_loaded_at < 86400:
        return _asset_ids
    response = requests.get(f"{COINLORE_BASE}/assets/", timeout=60)
    response.raise_for_status()
    mapping: dict[str, str] = {}
    for item in response.json() or []:
        symbol = str(item.get("symbol") or "").strip().upper()
        coin_id = str(item.get("id") or "").strip()
        if symbol and coin_id and symbol not in mapping:
            mapping[symbol] = coin_id
    _asset_ids = mapping
    _assets_loaded_at = now
    return mapping


def _fetch_ticker_page(start: int) -> tuple[list[dict], int]:
    response = requests.get(
        f"{COINLORE_BASE}/tickers/",
        params={"start": start, "limit": TICKER_PAGE_SIZE},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json() or {}
    data = payload.get("data") or []
    total = int((payload.get("info") or {}).get("coins_num") or 0)
    return data, total


def _fetch_ticker_by_id(coin_id: str) -> Decimal | None:
    response = requests.get(f"{COINLORE_BASE}/ticker/", params={"id": coin_id}, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if not payload:
        return None
    item = payload[0] if isinstance(payload, list) else payload
    return _parse_price(item.get("price_usd"))


def refresh_crypto_rates(symbols: Iterable[str] | None = None) -> int:
    wanted = {str(item or "").strip().upper() for item in (symbols or collect_tracked_symbols()) if str(item or "").strip()}
    if not wanted:
        wanted = set(STABLECOINS)

    found: dict[str, Decimal] = {sym: Decimal("1") for sym in wanted if sym in STABLECOINS}
    remaining = wanted - set(found.keys())

    start = 0
    pages = 0
    total = 0
    while remaining and pages < MAX_TICKER_PAGES:
        data, total = _fetch_ticker_page(start)
        pages += 1
        if not data:
            break
        for item in data:
            symbol = str(item.get("symbol") or "").strip().upper()
            if symbol not in remaining:
                continue
            price = _parse_price(item.get("price_usd"))
            if price is None:
                continue
            found[symbol] = price
            remaining.discard(symbol)
        if not remaining:
            break
        start += TICKER_PAGE_SIZE
        if total and start >= total:
            break
        _sleep_between_requests()

    if remaining:
        asset_ids = _load_asset_ids()
        for symbol in sorted(remaining):
            coin_id = asset_ids.get(symbol)
            if not coin_id:
                continue
            try:
                price = _fetch_ticker_by_id(coin_id)
            except requests.RequestException:
                logger.warning("CoinLore ticker fetch failed for %s", symbol)
                continue
            if price is None:
                continue
            found[symbol] = price
            remaining.discard(symbol)
            _sleep_between_requests()

    with _lock:
        _prices_usd.update(found)
        global _updated_at
        _updated_at = time.time()

    if remaining:
        logger.warning("CoinLore: no USD price for symbols: %s", ", ".join(sorted(remaining)))
    logger.info("CoinLore rates refreshed: %s symbols cached", len(_prices_usd))
    return len(found)


def cache_age_seconds() -> float:
    with _lock:
        if _updated_at <= 0:
            return -1.0
        return max(0.0, time.time() - _updated_at)


def get_usd_price(symbol: str) -> Decimal | None:
    sym = str(symbol or "").strip().upper()
    if not sym:
        return None
    if sym in STABLECOINS:
        return Decimal("1")
    with _lock:
        return _prices_usd.get(sym)


def usd_to_crypto_amount(usd_amount: str | Decimal, symbol: str) -> str:
    sym = str(symbol or "").strip().upper()
    try:
        usd = Decimal(str(usd_amount).strip().replace(",", "."))
    except InvalidOperation as exc:
        raise CryptoRatesError("Сумма USD должна быть числом") from exc
    if usd <= 0:
        raise CryptoRatesError("Сумма USD должна быть больше нуля")

    price = get_usd_price(sym)
    if price is None:
        age = cache_age_seconds()
        if age < 0:
            raise CryptoRatesError(f"Курс {sym} ещё не загружен. Подождите минуту и попробуйте снова.")
        raise CryptoRatesError(f"Курс {sym} не найден (CoinLore). Проверьте символ или попробуйте позже.")

    crypto_amount = usd / price
    if crypto_amount <= 0:
        raise CryptoRatesError(f"Не удалось рассчитать сумму в {sym}")
    return _format_crypto_amount(crypto_amount, sym)


def crypto_choice_label(*, currency: str, network: str, usd_amount: str) -> str:
    sym = currency.upper()
    try:
        amount = usd_to_crypto_amount(usd_amount, sym)
        return f"{sym} ({network}) ≈ {amount} {sym}"
    except CryptoRatesError:
        return f"{sym} ({network})"


async def run_crypto_rates_loop() -> None:
    try:
        await asyncio.to_thread(refresh_crypto_rates)
    except Exception:
        logger.exception("Initial CoinLore rates refresh failed")
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(refresh_crypto_rates)
        except Exception:
            logger.exception("CoinLore rates refresh failed")
