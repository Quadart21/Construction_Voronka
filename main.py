import asyncio
import logging

import uvicorn

from backend.api import app
from backend.bootstrap import bootstrap_application
from backend.bot_manager import start_all_bots, stop_all_bots
from backend.config import settings

logger = logging.getLogger(__name__)


async def run_bots() -> None:
    await start_all_bots()
    from backend.bootstrap import active_bot_count

    n = active_bot_count()
    if n == 0:
        logger.error(
            "No Telegram bots started. Add a bot in admin (Мои боты) or set BOT_TOKEN in .env and restart."
        )
    else:
        logger.info("Telegram polling active for %s bot(s)", n)
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await stop_all_bots()


async def run_api() -> None:
    config = uvicorn.Config(app, host=settings.api_host, port=settings.api_port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    bootstrap_application()
    await asyncio.gather(run_api(), run_bots())


if __name__ == "__main__":
    asyncio.run(main())
