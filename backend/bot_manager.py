import asyncio
import logging

from sqlalchemy import select

from backend.bot import build_bot_application
from backend.config import settings
from backend.database import session_scope
from backend.models import TelegramBot
from backend.runtime import clear_bot_applications, get_all_bot_applications, set_bot_application

logger = logging.getLogger(__name__)

_polling_tasks: dict[int, asyncio.Task] = {}


async def _poll_bot(application, bot_id: int) -> None:
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    set_bot_application(application, bot_id)
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        raise
    finally:
        try:
            await application.updater.stop()
        except Exception:
            pass
        try:
            await application.stop()
        except Exception:
            pass
        try:
            await application.shutdown()
        except Exception:
            pass


async def stop_bot(bot_id: int) -> None:
    task = _polling_tasks.pop(int(bot_id), None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def start_bot_record(bot: TelegramBot) -> None:
    token = (bot.token or "").strip()
    if not bot.is_active or not token or token == "REPLACE_ME":
        await stop_bot(bot.id)
        return
    await stop_bot(bot.id)
    application = build_bot_application(token, bot.id)
    task = asyncio.create_task(_poll_bot(application, bot.id), name=f"bot-poll-{bot.id}")
    _polling_tasks[int(bot.id)] = task


async def start_all_bots() -> None:
    with session_scope() as session:
        bots = list(session.scalars(select(TelegramBot).where(TelegramBot.is_active.is_(True)).order_by(TelegramBot.sort_order, TelegramBot.id)))
    if not bots:
        return
    for bot in bots:
        try:
            await start_bot_record(bot)
        except Exception:
            logger.exception("Failed to start bot id=%s", bot.id)


async def stop_all_bots() -> None:
    for bot_id in list(_polling_tasks.keys()):
        await stop_bot(bot_id)
    clear_bot_applications()


async def reload_bot(bot_id: int) -> None:
    with session_scope() as session:
        bot = session.get(TelegramBot, bot_id)
        if bot is None:
            await stop_bot(bot_id)
            return
        await start_bot_record(bot)


async def reload_all_bots() -> None:
    await stop_all_bots()
    await start_all_bots()
