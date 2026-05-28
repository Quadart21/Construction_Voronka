"""SQLite-safe migration: several Telegram bots, each with its own funnel."""

from sqlalchemy import inspect, select, text

from backend.config import settings
from backend.database import engine, session_scope
from backend.models import TelegramBot


BOT_SCOPED_TABLES = (
    "users",
    "segments",
    "follow_up_messages",
    "funnel_steps",
    "funnel_branches",
    "automation_rules",
    "payment_records",
    "app_settings",
)


def _table_columns(table: str) -> set[str]:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _add_bot_id_column(table: str) -> None:
    if "bot_id" in _table_columns(table):
        return
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN bot_id INTEGER NOT NULL DEFAULT 1"))


def _ensure_default_bot() -> int:
    with session_scope() as session:
        existing = session.scalar(select(TelegramBot.id).order_by(TelegramBot.sort_order, TelegramBot.id).limit(1))
        if existing is not None:
            return int(existing)
        token = (settings.bot_token or "").strip()
        entity = TelegramBot(
            name="Основной бот",
            token=token or "REPLACE_ME",
            is_active=bool(token),
            sort_order=0,
        )
        session.add(entity)
        session.flush()
        return int(entity.id)


def _rebuild_users_table(default_bot_id: int) -> None:
    cols = _table_columns("users")
    if "bot_id" in cols and "telegram_id" in cols:
        indexes = {idx["name"] for idx in inspect(engine).get_indexes("users")}
        if any("telegram_id" in str(idx) and "bot_id" not in str(idx) for idx in inspect(engine).get_indexes("users")):
            pass
    if "bot_id" in cols:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY,
                    bot_id INTEGER NOT NULL DEFAULT 1,
                    telegram_id INTEGER NOT NULL,
                    username VARCHAR(128),
                    full_name VARCHAR(255) DEFAULT '',
                    segment_key VARCHAR(64),
                    current_step VARCHAR(64) DEFAULT 'start',
                    source VARCHAR(64) DEFAULT 'instagram',
                    is_customer BOOLEAN DEFAULT 0,
                    anti_spam_hits INTEGER DEFAULT 0,
                    anti_spam_last_hit_at DATETIME,
                    created_at DATETIME,
                    updated_at DATETIME,
                    UNIQUE (bot_id, telegram_id)
                )
                """
            )
        )
        connection.execute(
            text(
                f"""
                INSERT INTO users_new (
                    id, bot_id, telegram_id, username, full_name, segment_key, current_step, source,
                    is_customer, anti_spam_hits, anti_spam_last_hit_at, created_at, updated_at
                )
                SELECT
                    id, {default_bot_id}, telegram_id, username, full_name, segment_key, current_step, source,
                    is_customer, anti_spam_hits, anti_spam_last_hit_at, created_at, updated_at
                FROM users
                """
            )
        )
        connection.execute(text("DROP TABLE users"))
        connection.execute(text("ALTER TABLE users_new RENAME TO users"))


def _rebuild_unique_table(table: str, *, create_sql: str, copy_sql: str, default_bot_id: int) -> None:
    cols = _table_columns(table)
    if "bot_id" in cols:
        return
    with engine.begin() as connection:
        connection.execute(text(create_sql.format(bot_id=default_bot_id)))
        connection.execute(text(copy_sql.format(bot_id=default_bot_id)))
        connection.execute(text(f"DROP TABLE {table}"))
        connection.execute(text(f"ALTER TABLE {table}_new RENAME TO {table}"))


def _migrate_legacy_unique_tables(default_bot_id: int) -> None:
    if "bot_id" not in _table_columns("funnel_steps"):
        _rebuild_unique_table(
            "funnel_steps",
            create_sql="""
                CREATE TABLE funnel_steps_new (
                    id INTEGER PRIMARY KEY,
                    bot_id INTEGER NOT NULL DEFAULT {bot_id},
                    code VARCHAR(64) NOT NULL,
                    title VARCHAR(255),
                    body TEXT,
                    step_type VARCHAR(32) DEFAULT 'content',
                    media_type VARCHAR(32),
                    media_url TEXT,
                    media_caption TEXT,
                    segment_key VARCHAR(64),
                    cta_text VARCHAR(128),
                    next_step_code VARCHAR(64),
                    trigger_keywords TEXT,
                    funnel_phase VARCHAR(32) DEFAULT 'main',
                    sort_order INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE (bot_id, code)
                )
            """,
            copy_sql="""
                INSERT INTO funnel_steps_new (
                    id, bot_id, code, title, body, step_type, media_type, media_url, media_caption,
                    segment_key, cta_text, next_step_code, trigger_keywords, funnel_phase, sort_order, is_active
                )
                SELECT
                    id, {bot_id}, code, title, body, step_type, media_type, media_url, media_caption,
                    segment_key, cta_text, next_step_code, trigger_keywords,
                    COALESCE(NULLIF(funnel_phase, ''), 'main'), sort_order, is_active
                FROM funnel_steps
            """,
            default_bot_id=default_bot_id,
        )

    if "bot_id" not in _table_columns("app_settings"):
        _rebuild_unique_table(
            "app_settings",
            create_sql="""
                CREATE TABLE app_settings_new (
                    id INTEGER PRIMARY KEY,
                    bot_id INTEGER NOT NULL DEFAULT {bot_id},
                    key VARCHAR(128) NOT NULL,
                    value JSON,
                    UNIQUE (bot_id, key)
                )
            """,
            copy_sql="""
                INSERT INTO app_settings_new (id, bot_id, key, value)
                SELECT id, {bot_id}, key, value FROM app_settings
            """,
            default_bot_id=default_bot_id,
        )


def ensure_multi_bot_schema() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "telegram_bots" not in tables:
        TelegramBot.__table__.create(bind=engine, checkfirst=True)

    default_bot_id = _ensure_default_bot()

    if "users" in tables and "bot_id" not in _table_columns("users"):
        _rebuild_users_table(default_bot_id)
    else:
        _add_bot_id_column("users")

    for table in BOT_SCOPED_TABLES:
        if table in tables:
            _add_bot_id_column(table)

    _migrate_legacy_unique_tables(default_bot_id)

    with engine.begin() as connection:
        for table in BOT_SCOPED_TABLES:
            if table in _table_columns(table):
                connection.execute(text(f"UPDATE {table} SET bot_id = :bot_id WHERE bot_id IS NULL OR bot_id = 0"), {"bot_id": default_bot_id})

