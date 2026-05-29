"""One-time DB init before API and Telegram polling start."""

import logging

from sqlalchemy import inspect, select, text

from backend.config import settings
from backend.database import Base, engine, session_scope
from backend.models import TelegramBot
from backend.multi_bot_migrate import ensure_multi_bot_schema
from backend.seed import seed_defaults

logger = logging.getLogger(__name__)


def ensure_runtime_columns() -> None:
    if "funnel_steps" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("funnel_steps")}
    if "trigger_keywords" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE funnel_steps ADD COLUMN trigger_keywords TEXT"))
    if "funnel_phase" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE funnel_steps ADD COLUMN funnel_phase VARCHAR(32) DEFAULT 'main'"))
            connection.execute(
                text("UPDATE funnel_steps SET funnel_phase = 'main' WHERE funnel_phase IS NULL OR funnel_phase = ''")
            )


def _token_is_valid(token: str | None) -> bool:
    value = (token or "").strip()
    return bool(value) and value != "REPLACE_ME"


def _read_bot_token_from_env_file() -> str:
    if _token_is_valid(settings.bot_token):
        return settings.bot_token.strip()
    env_path = settings.data_dir.parent / ".env"
    if not env_path.is_file():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "BOT_TOKEN":
            return value.strip().strip('"').strip("'")
    return ""


def sync_bot_tokens_from_env() -> None:
    """Optional: copy BOT_TOKEN from .env into first bot if DB token is empty (legacy)."""
    with session_scope() as session:
        bots = list(session.scalars(select(TelegramBot).order_by(TelegramBot.sort_order, TelegramBot.id)))
        has_valid = any(_token_is_valid(bot.token) and bot.is_active for bot in bots)
        if has_valid:
            return

    env_token = _read_bot_token_from_env_file()
    if env_token:
        with session_scope() as session:
            bots = list(session.scalars(select(TelegramBot).order_by(TelegramBot.sort_order, TelegramBot.id)))
            if not bots:
                session.add(
                    TelegramBot(
                        name="Основной бот",
                        token=env_token,
                        is_active=True,
                        sort_order=0,
                    )
                )
                logger.info("Created default bot record from BOT_TOKEN in .env")
                return
            primary = bots[0]
            primary.token = env_token
            primary.is_active = True
            logger.info("Updated bot id=%s from BOT_TOKEN in .env", primary.id)
        return

    if bots:
        logger.warning(
            "No bot tokens in database. Open admin → Мои боты → paste token from @BotFather → Save."
        )


def bootstrap_application() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    ensure_runtime_columns()
    ensure_multi_bot_schema()
    sync_bot_tokens_from_env()
    seed_defaults()


def active_bot_count() -> int:
    with session_scope() as session:
        bots = list(session.scalars(select(TelegramBot).where(TelegramBot.is_active.is_(True))))
    return sum(1 for bot in bots if _token_is_valid(bot.token))
