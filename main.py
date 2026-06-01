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
            "No Telegram bots polling. Add token in admin panel: Мои боты → token from @BotFather → Save."
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
    from backend.crypto_rates import run_crypto_rates_loop

    await asyncio.gather(run_api(), run_bots(), run_crypto_rates_loop())


if __name__ == "__main__":
    asyncio.run(main())
