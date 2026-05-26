from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from backend.config import settings
from backend.formatting import html_media_caption, html_message
from backend.media import send_media


def delivery_keyboard(delivery: dict) -> InlineKeyboardMarkup | None:
    buttons = []
    for item in delivery.get("buttons") or []:
        text = str(item.get("text") or "").strip()
        url = str(item.get("url") or "").strip()
        if text and url:
            buttons.append([InlineKeyboardButton(text, url=url)])
    return InlineKeyboardMarkup(buttons) if buttons else None


async def send_paid_delivery(bot: Bot, *, chat_id: int, offer: dict) -> None:
    delivery = offer.get("delivery") or {}
    title = delivery.get("title") or "Доступ открыт"
    text = delivery.get("text") or "Оплата прошла. Держи материалы, которые ты купил."
    message_text = html_message(title, text)
    keyboard = delivery_keyboard(delivery)
    media_type = str(delivery.get("media_type") or "").strip()
    media_url = str(delivery.get("media_url") or "").strip()

    if media_type and media_url:
        try:
            await send_media(
                bot,
                chat_id=chat_id,
                media_type=media_type,
                media_url=media_url,
                caption=html_media_caption(title, text, delivery.get("media_caption")),
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
                protect_content=settings.content_protection_enabled,
            )
            return
        except Exception:
            pass

    await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )
