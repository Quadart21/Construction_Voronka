import asyncio

import uvicorn

from backend.api import app
from backend.bot_manager import start_all_bots, stop_all_bots
from backend.config import settings


async def run_bots() -> None:
    await start_all_bots()
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
    await asyncio.gather(run_api(), run_bots())


if __name__ == "__main__":
    asyncio.run(main())
