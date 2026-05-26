from urllib.parse import urljoin

import requests

from backend.config import settings


def create_platega_payment_link(*, amount: int, currency: str, description: str, payload: str, payment_method: int = 2) -> dict:
    if not settings.platega_merchant_id or not settings.platega_secret:
        raise RuntimeError("Platega credentials are not configured")

    payload_body = {
        "paymentMethod": payment_method,
        "paymentDetails": {"amount": amount, "currency": currency},
        "description": description,
        "return": settings.platega_return_url,
        "failedUrl": settings.platega_failed_url,
        "payload": payload,
    }
    if settings.platega_callback_url:
        payload_body["callbackUrl"] = settings.platega_callback_url

    response = requests.post(
        urljoin(settings.platega_base_url.rstrip("/") + "/", "transaction/process"),
        headers={
            "Content-Type": "application/json",
            "X-MerchantId": settings.platega_merchant_id,
            "X-Secret": settings.platega_secret,
        },
        json=payload_body,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
