import asyncio

import uvicorn

from backend.api import app
from backend.bot import build_bot_application
from backend.config import settings


async def run_bot() -> None:
    if not settings.bot_token:
        return
    application = build_bot_application()
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


async def run_api() -> None:
    config = uvicorn.Config(app, host=settings.api_host, port=settings.api_port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    await asyncio.gather(run_api(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
