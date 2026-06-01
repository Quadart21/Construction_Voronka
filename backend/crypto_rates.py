from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable

import requests
from sqlalchemy import func, select

from backend.database import session_scope
from backend.models import AppSetting, CryptoExchangeRate
from backend.payment_settings import normalize_payment_settings

logger = logging.getLogger(__name__)

COINLORE_BASE = "https://api.coinlore.net/api"
REFRESH_INTERVAL_SECONDS = 300
REQUEST_GAP_SECONDS = 1.05
MAX_TICKER_PAGES = 20
TICKER_PAGE_SIZE = 100

STABLECOINS = frozenset({"USDT", "USDC", "BUSD", "DAI", "TUSD", "USDD", "FDUSD", "USDP", "PYUSD"})

_asset_ids: dict[str, str] = {}
_assets_loaded_at: float = 0.0


class CryptoRatesError(RuntimeError):
    pass


def symbols_from_allowed_cryptos(allowed_cryptos: Iterable[str] | None) -> set[str]:
    symbols: set[str] = set()
    for item in allowed_cryptos or []:
        if isinstance(item, str) and "|" in item:
            currency = item.split("|", 1)[0].strip().upper()
            if currency:
                symbols.add(currency)
    return symbols


def collect_tracked_symbols() -> set[str]:
    symbols = set(STABLECOINS)
    with session_scope() as session:
        rows = session.scalars(select(AppSetting).where(AppSetting.key == "payment"))
        for row in rows:
            payment = normalize_payment_settings(row.value)
            symbols.update(symbols_from_allowed_cryptos(payment["noren"].get("allowed_cryptos")))
    return symbols


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


def _fetch_coinlore_prices(symbols: Iterable[str]) -> dict[str, Decimal]:
    wanted = {str(item or "").strip().upper() for item in symbols if str(item or "").strip()}
    if not wanted:
        return {}

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

    if remaining:
        logger.warning("CoinLore: no USD price for symbols: %s", ", ".join(sorted(remaining)))
    return found


def save_rates_to_db(rates: dict[str, Decimal]) -> int:
    if not rates:
        return 0
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        for symbol, price in rates.items():
            row = session.get(CryptoExchangeRate, symbol)
            price_str = format(price.normalize(), "f")
            if row is None:
                session.add(CryptoExchangeRate(currency=symbol, price_usdt=price_str, updated_at=now))
            else:
                row.price_usdt = price_str
                row.updated_at = now
    return len(rates)


def refresh_crypto_rates(symbols: Iterable[str] | None = None) -> int:
    wanted = {str(item or "").strip().upper() for item in (symbols or collect_tracked_symbols()) if str(item or "").strip()}
    if not wanted:
        wanted = set(STABLECOINS)
    found = _fetch_coinlore_prices(wanted)
    saved = save_rates_to_db(found)
    logger.info("CoinLore rates saved to DB: %s symbols", saved)
    return saved


def list_stored_rates(*, symbols: Iterable[str] | None = None) -> list[dict]:
    filter_symbols = None
    if symbols is not None:
        filter_symbols = {str(item or "").strip().upper() for item in symbols if str(item or "").strip()}
    with session_scope() as session:
        rows = list(session.scalars(select(CryptoExchangeRate).order_by(CryptoExchangeRate.currency)))
    items = []
    for row in rows:
        if filter_symbols is not None and row.currency not in filter_symbols:
            continue
        items.append(
            {
                "currency": row.currency,
                "price_usdt": row.price_usdt,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )
    return items


def cache_age_seconds() -> float:
    with session_scope() as session:
        updated_at = session.scalar(select(func.max(CryptoExchangeRate.updated_at)))
    if updated_at is None:
        return -1.0
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - updated_at.astimezone(timezone.utc)).total_seconds())


def get_usd_price(symbol: str) -> Decimal | None:
    sym = str(symbol or "").strip().upper()
    if not sym:
        return None
    if sym in STABLECOINS:
        return Decimal("1")
    with session_scope() as session:
        row = session.get(CryptoExchangeRate, sym)
        if row is None:
            return None
        return _parse_price(row.price_usdt)


def usd_to_crypto_decimal(usd_amount: str | Decimal, symbol: str) -> Decimal:
    return Decimal(usd_to_crypto_amount(usd_amount, symbol))


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
        raise CryptoRatesError(
            f"Курс {sym} не найден в базе. Сохраните настройки оплаты или подождите обновления (каждые 5 мин)."
        )

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
    from backend.noren_limits import refresh_noren_deposit_limits

    try:
        await asyncio.to_thread(refresh_crypto_rates)
    except Exception:
        logger.exception("Initial CoinLore rates refresh failed")
    try:
        await asyncio.to_thread(refresh_noren_deposit_limits)
    except Exception:
        logger.exception("Initial Noren deposit limits refresh failed")
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(refresh_crypto_rates)
        except Exception:
            logger.exception("CoinLore rates refresh failed")
        try:
            await asyncio.to_thread(refresh_noren_deposit_limits)
        except Exception:
            logger.exception("Noren deposit limits refresh failed")
