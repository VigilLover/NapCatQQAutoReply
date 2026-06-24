import asyncio
import logging
import sys

from dotenv import load_dotenv

from .app import run_bot
from .config import AppConfig


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    load_dotenv()
    config = AppConfig.from_env()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_bot(config))


if __name__ == "__main__":
    run()
