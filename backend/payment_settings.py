def normalize_payment_settings(raw: dict | None) -> dict:
    data = dict(raw or {})
    platega = dict(data.get("platega") or {})
    if "enabled" not in platega:
        platega["enabled"] = data.get("enabled", True) is not False
    noren = dict(data.get("noren") or {})
    if "enabled" not in noren:
        noren["enabled"] = False
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
