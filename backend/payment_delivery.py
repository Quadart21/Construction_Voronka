from datetime import datetime

from sqlalchemy import select
from telegram import Bot

from backend.database import session_scope
from backend.models import PaymentRecord, TelegramBot, User
from backend.post_payment import deliver_after_payment
from backend.runtime import get_bot_application
from backend.services import get_setting, log_event


def payment_payload_meta(payload: dict | None) -> dict:
    data = payload or {}
    local = data.get("local")
    if isinstance(local, dict):
        return local
    raw = str(data.get("payload") or "")
    result = {}
    for chunk in raw.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        result[key.strip()] = value.strip()
    return result


async def finalize_paid_payment(
    *,
    transaction_id: str,
    status: str,
    payload_extra: dict | None = None,
    amount: int | None = None,
    currency: str | None = None,
) -> dict:
    delivery_target: int | None = None
    delivery_bot_id: int | None = None
    offer: dict = {}

    with session_scope() as session:
        record = session.scalar(select(PaymentRecord).where(PaymentRecord.transaction_id == transaction_id)) if transaction_id else None
        if record is None:
            return {"ok": True, "matched": False}

        previous_status = record.status
        record.status = status
        record.payload = {**(record.payload or {}), "webhook_at": datetime.utcnow().isoformat()}
        if payload_extra:
            record.payload = {**(record.payload or {}), **payload_extra}
        if amount is not None:
            record.amount = amount
        if currency is not None:
            record.currency = currency

        record_bot_id = int(record.bot_id or 1)
        payment_meta = payment_payload_meta(record.payload)
        if payment_meta.get("bot_id"):
            record_bot_id = int(payment_meta["bot_id"])
        user = (
            session.get(User, record.user_id)
            if record.user_id
            else session.scalar(select(User).where(User.bot_id == record_bot_id, User.telegram_id == record.telegram_id))
        )
        paid_step = str(payment_meta.get("step") or user.current_step if user else "payment").strip() or "payment"
        if user and status == "paid":
            user.is_customer = True
            if previous_status != "paid":
                log_event(session, user, "payment_paid", paid_step, {"transaction_id": transaction_id})
            if not (record.payload or {}).get("delivery_sent_at"):
                delivery_target = user.telegram_id
                delivery_bot_id = record_bot_id
        elif user and status in {"failed", "refunded"} and previous_status != status:
            log_event(session, user, f"payment_{status}", paid_step, {"transaction_id": transaction_id})

        offer = get_setting(session, "offer", record_bot_id) if delivery_target else {}

    if delivery_target and delivery_bot_id:
        application = get_bot_application(delivery_bot_id)
        bot_token = None
        if application is None:
            with session_scope() as session:
                bot_row = session.get(TelegramBot, delivery_bot_id)
                bot_token = bot_row.token if bot_row else None
        if application is not None:
            await deliver_after_payment(
                application=application,
                chat_id=delivery_target,
                telegram_id=delivery_target,
                offer=offer,
            )
        elif bot_token:
            from backend.delivery import send_paid_delivery

            async with Bot(bot_token) as bot:
                await send_paid_delivery(bot, chat_id=delivery_target, offer=offer)
        with session_scope() as session:
            record = session.scalar(select(PaymentRecord).where(PaymentRecord.transaction_id == transaction_id))
            user = session.scalar(select(User).where(User.bot_id == delivery_bot_id, User.telegram_id == delivery_target))
            if record is not None:
                record.payload = {**(record.payload or {}), "delivery_sent_at": datetime.utcnow().isoformat()}
            if user is not None:
                paid_step = str(
                    payment_payload_meta(record.payload if record else {}).get("step") or user.current_step or "payment"
                )
                log_event(session, user, "paid_delivery_sent", paid_step, {"transaction_id": transaction_id})

    return {"ok": True, "matched": True, "status": status}
