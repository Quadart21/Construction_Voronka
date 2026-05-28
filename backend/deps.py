from fastapi import HTTPException, Query
from sqlalchemy import select

from backend.database import session_scope
from backend.models import TelegramBot


def mask_bot_token(token: str) -> str:
    value = (token or "").strip()
    if len(value) < 12:
        return "••••••••"
    return f"{value[:8]}…{value[-4:]}"


def resolve_bot_id(bot_id: int | None = Query(None, alias="bot_id")) -> int:
    with session_scope() as session:
        if bot_id is not None:
            entity = session.get(TelegramBot, bot_id)
            if entity is None:
                raise HTTPException(status_code=404, detail="Бот не найден")
            return int(entity.id)
        entity = session.scalar(
            select(TelegramBot).where(TelegramBot.is_active.is_(True)).order_by(TelegramBot.sort_order, TelegramBot.id).limit(1)
        )
        if entity is None:
            entity = session.scalar(select(TelegramBot).order_by(TelegramBot.sort_order, TelegramBot.id).limit(1))
        if entity is None:
            raise HTTPException(status_code=400, detail="Сначала добавьте Telegram-бота в админке")
        return int(entity.id)
