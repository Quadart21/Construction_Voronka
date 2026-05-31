from backend.config import settings


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
            "amount": str(noren.get("amount") or "").strip(),
            "crypto_currency": str(noren.get("crypto_currency") or "USDT").strip().upper(),
            "network": str(noren.get("network") or "TRC20").strip().upper(),
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
    if noren["enabled"] and noren["api_key"] and noren["api_secret"] and noren["project_id"] and noren["amount"]:
        methods.append("noren")
    return methods
