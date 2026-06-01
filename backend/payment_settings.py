from backend.config import settings


def _normalize_allowed_cryptos(raw) -> list[str]:
    keys: list[str] = []
    for item in raw or []:
        if isinstance(item, str) and "|" in item:
            currency, network = item.split("|", 1)
            key = f"{currency.strip().upper()}|{network.strip().upper()}"
            if currency.strip() and network.strip() and key not in keys:
                keys.append(key)
        elif isinstance(item, dict):
            currency = str(item.get("currency") or "").strip().upper()
            network = str(item.get("network") or "").strip().upper()
            if currency and network:
                key = f"{currency}|{network}"
                if key not in keys:
                    keys.append(key)
    return keys


def normalize_payment_settings(raw: dict | None) -> dict:
    data = dict(raw or {})
    platega = dict(data.get("platega") or {})
    if "enabled" not in platega:
        platega["enabled"] = data.get("enabled", True) is not False
    noren = dict(data.get("noren") or {})
    if "enabled" not in noren:
        noren["enabled"] = False
    if str(settings.payment_provider or "").strip().lower() == "crypto_cash":
        noren["enabled"] = True
    return {
        "platega": {
            "enabled": platega.get("enabled", True) is not False,
        },
        "noren": {
            "enabled": noren.get("enabled", False) is True,
            "api_key": str(noren.get("api_key") or "").strip(),
            "api_secret": str(noren.get("api_secret") or "").strip(),
            "project_id": str(noren.get("project_id") or "").strip(),
            "base_url": str(noren.get("base_url") or "https://noren.digital/api/v1/client").strip().rstrip("/"),
            "price": str(noren.get("price") or noren.get("amount") or "").strip(),
            "price_currency": str(noren.get("price_currency") or "USD").strip().upper(),
            "usd_rub_rate": str(noren.get("usd_rub_rate") or "").strip(),
            "allowed_cryptos": _normalize_allowed_cryptos(noren.get("allowed_cryptos")),
            "webhook_secret": str(noren.get("webhook_secret") or "").strip(),
            "invoice_reuse_active": noren.get("invoice_reuse_active") is not False,
            "invoice_max_per_hour": max(1, int(noren.get("invoice_max_per_hour") or 3)),
            "invoice_cooldown_minutes": max(0, int(noren.get("invoice_cooldown_minutes") or 5)),
        },
    }


def enabled_payment_methods(payment: dict) -> list[str]:
    normalized = normalize_payment_settings(payment)
    methods: list[str] = []
    if normalized["platega"]["enabled"]:
        methods.append("platega")
    noren = normalized["noren"]
    if noren["enabled"] and noren["api_key"] and noren["api_secret"] and noren["project_id"] and noren["price"] and noren["allowed_cryptos"]:
        methods.append("noren")
    return methods
