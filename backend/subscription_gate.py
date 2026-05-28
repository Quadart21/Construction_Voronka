from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from backend.config import settings
from backend.formatting import html_message

SUBSCRIBED_STATUSES = {"member", "administrator", "creator"}


def _normalize_channel(raw: dict | None, *, index: int = 0) -> dict:
    item = dict(raw or {})
    channel_id = str(item.get("channel_id") or "").strip()
    title = str(item.get("title") or "").strip() or f"Канал {index + 1}"
    subscribe_url = str(item.get("subscribe_url") or "").strip()
    return {"channel_id": channel_id, "title": title, "subscribe_url": subscribe_url}


def _channels_from_legacy(gate: dict) -> list[dict]:
    legacy_id = str(gate.get("channel_id") or "").strip()
    if not legacy_id:
        return []
    legacy_url = str(gate.get("subscribe_url") or "").strip()
    legacy_title = str(gate.get("subscribe_button_text") or "").strip() or "Подписаться"
    return [{"channel_id": legacy_id, "title": legacy_title, "subscribe_url": legacy_url}]


def normalize_gate(raw: dict | None) -> dict:
    gate = dict(raw or {})
    channels_raw = gate.get("channels")
    if isinstance(channels_raw, list) and channels_raw:
        channels = [_normalize_channel(item, index=i) for i, item in enumerate(channels_raw) if isinstance(item, dict)]
        channels = [item for item in channels if item["channel_id"]]
    else:
        channels = _channels_from_legacy(gate)

    return {
        "enabled": bool(gate.get("enabled")),
        "channels": channels,
        "require_all": gate.get("require_all", True) is not False,
        "message": str(
            gate.get("message") or "Чтобы пользоваться ботом, подпишитесь на наши каналы — там материалы и анонсы."
        ).strip(),
        "not_subscribed_hint": str(
            gate.get("not_subscribed_hint")
            or "Подписка пока не видна. Откройте каналы, подпишитесь и нажмите «Проверить»."
        ).strip(),
        "check_button_text": str(gate.get("check_button_text") or "Я подписался — проверить").strip(),
        "skip_for_paid_users": gate.get("skip_for_paid_users", True) is not False,
    }


def gate_is_active(gate: dict) -> bool:
    normalized = normalize_gate(gate)
    return normalized["enabled"] and bool(normalized["channels"])


def subscribe_url_for_channel(channel: dict) -> str:
    url = str(channel.get("subscribe_url") or "").strip()
    if url.startswith(("http://", "https://")):
        return url
    channel_id = str(channel.get("channel_id") or "").strip()
    if channel_id.startswith("@"):
        return f"https://t.me/{channel_id.lstrip('@')}"
    return url or "https://t.me/"


def subscription_keyboard(gate: dict) -> InlineKeyboardMarkup:
    normalized = normalize_gate(gate)
    rows: list[list[InlineKeyboardButton]] = []
    for channel in normalized["channels"]:
        url = subscribe_url_for_channel(channel)
        if not url.startswith(("http://", "https://")):
            url = "https://t.me/"
        label = channel["title"] or "Подписаться"
        rows.append([InlineKeyboardButton(label, url=url)])
    rows.append([InlineKeyboardButton(normalized["check_button_text"], callback_data="check_sub")])
    return InlineKeyboardMarkup(rows)


async def is_user_subscribed_to_channel(bot: Bot, channel_id: str, user_id: int) -> bool:
    if not channel_id:
        return True
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
    except Exception:
        return False
    if member.status in SUBSCRIBED_STATUSES:
        return True
    if member.status == "restricted":
        return bool(getattr(member, "is_member", False))
    return False


async def check_user_subscriptions(bot: Bot, gate: dict, user_id: int) -> tuple[bool, list[str]]:
    """Возвращает (доступ разрешён, список названий каналов без подписки)."""
    normalized = normalize_gate(gate)
    channels = normalized["channels"]
    if not channels:
        return True, []

    missing: list[str] = []
    subscribed_any = False
    for channel in channels:
        ok = await is_user_subscribed_to_channel(bot, channel["channel_id"], user_id)
        if ok:
            subscribed_any = True
        else:
            missing.append(channel["title"] or channel["channel_id"])

    if normalized["require_all"]:
        return (len(missing) == 0, missing)
    return (subscribed_any, missing if not subscribed_any else [])


def subscription_check_hint(gate: dict, missing_titles: list[str]) -> str:
    base = normalize_gate(gate)["not_subscribed_hint"]
    if not missing_titles:
        return base
    listed = ", ".join(missing_titles[:5])
    suffix = f" Не хватает: {listed}."
    if len(missing_titles) > 5:
        suffix += "…"
    return f"{base}{suffix}"


async def send_subscription_prompt(bot: Bot, *, chat_id: int, gate: dict) -> None:
    normalized = normalize_gate(gate)
    await bot.send_message(
        chat_id=chat_id,
        text=html_message("Нужна подписка", normalized["message"]),
        reply_markup=subscription_keyboard(normalized),
        parse_mode=ParseMode.HTML,
        protect_content=settings.content_protection_enabled,
    )
