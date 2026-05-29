"""One-time DB init before API and Telegram polling start."""

from sqlalchemy import inspect, select, text

from backend.config import settings
from backend.database import Base, engine, session_scope
from backend.models import TelegramBot
from backend.multi_bot_migrate import ensure_multi_bot_schema
from backend.seed import seed_defaults


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


def sync_bot_tokens_from_env() -> None:
    """Keep legacy BOT_TOKEN in .env working: push into telegram_bots if missing."""
    env_token = (settings.bot_token or "").strip()
    with session_scope() as session:
        bots = list(session.scalars(select(TelegramBot).order_by(TelegramBot.sort_order, TelegramBot.id)))
        if not bots:
            if env_token:
                session.add(
                    TelegramBot(
                        name="Основной бот",
                        token=env_token,
                        is_active=True,
                        sort_order=0,
                    )
                )
            return

        needs_token = [bot for bot in bots if not (bot.token or "").strip() or (bot.token or "").strip() == "REPLACE_ME"]
        if env_token and needs_token:
            primary = needs_token[0]
            primary.token = env_token
            primary.is_active = True
            if not (primary.name or "").strip():
                primary.name = "Основной бот"

        if env_token and not any(bot.is_active and (bot.token or "").strip() not in {"", "REPLACE_ME"} for bot in bots):
            primary = bots[0]
            primary.token = env_token
            primary.is_active = True


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
    return sum(1 for bot in bots if (bot.token or "").strip() not in {"", "REPLACE_ME"})
