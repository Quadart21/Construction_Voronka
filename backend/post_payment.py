from sqlalchemy import select

from backend.bot_context import bot_id_from
from backend.database import session_scope
from backend.delivery import send_paid_delivery
from backend.models import User
from backend.services import get_first_post_payment_step, get_setting, log_event


def delivery_has_content(delivery: dict) -> bool:
    if not delivery:
        return False
    return bool(
        str(delivery.get("title") or "").strip()
        or str(delivery.get("text") or "").strip()
        or str(delivery.get("media_url") or "").strip()
        or (delivery.get("buttons") or [])
    )


class _TelegramUserStub:
    def __init__(self, user: User):
        self.id = user.telegram_id
        self.username = user.username
        parts = (user.full_name or "").split()
        self.first_name = parts[0] if parts else "User"
        self.last_name = " ".join(parts[1:]) if len(parts) > 1 else None


async def deliver_after_payment(*, application, chat_id: int, telegram_id: int, offer: dict | None = None) -> None:
    """После успешной оплаты: опционально короткое сообщение, затем цепочка post_payment."""
    from backend.bot import render_step

    bot_id = bot_id_from(application)
    with session_scope() as session:
        user = session.scalar(select(User).where(User.bot_id == bot_id, User.telegram_id == telegram_id))
        offer = offer or get_setting(session, "offer", bot_id)
        delivery = offer.get("delivery") or {}
        send_before_chain = bool(delivery.get("send_before_chain"))
        first_step = get_first_post_payment_step(session, bot_id)
        user_stub = _TelegramUserStub(user) if user is not None else None

    if send_before_chain and delivery_has_content(delivery):
        await send_paid_delivery(application.bot, chat_id=chat_id, offer=offer)

    if first_step is not None and user_stub is not None:
        with session_scope() as session:
            user = session.scalar(select(User).where(User.bot_id == bot_id, User.telegram_id == telegram_id))
            if user is not None:
                log_event(session, user, "post_payment_chain_started", first_step.code, {})
        await render_step(
            application,
            chat_id,
            first_step.code,
            user_stub,
            event_type="post_payment_started",
        )
        return

    if not send_before_chain:
        await send_paid_delivery(application.bot, chat_id=chat_id, offer=offer)
