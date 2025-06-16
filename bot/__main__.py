from __future__ import annotations

import asyncio
import logging
from asyncio import CancelledError
from functools import partial
from typing import TYPE_CHECKING

import msgspec
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import PRODUCTION
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from bot import errors, handlers
from bot.db.mysql.base import close_db, create_db_session_pool, init_db
from bot.middlewares.check_user_middleware import CheckUserMiddleware
from bot.settings import Settings
from bot.scheduler import default_scheduler as scheduler
from bot.background_jobs import job_sec

if TYPE_CHECKING:
    from redis.asyncio import Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def startup(
    dispatcher: Dispatcher, bot: Bot, settings: Settings, redis: Redis
) -> None:
    await bot.delete_webhook(drop_pending_updates=True)

    engine, db_session = await create_db_session_pool(settings)

    await init_db(engine)

    dispatcher.workflow_data.update(
        {"sessionmaker": db_session, "db_session_closer": partial(close_db, engine)}
    )

    dispatcher.update.outer_middleware(CheckUserMiddleware())

    logger.info("Bot started")


async def shutdown(dispatcher: Dispatcher) -> None:
    await dispatcher["db_session_closer"]()
    logger.info("Bot stopped")


async def start_scheduler() -> None:
    scheduler.every(1).seconds.do(job_sec)
    while True:
        await scheduler.run_pending()
        await asyncio.sleep(1)


async def set_default_commands(bot: Bot):
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="start"),
            BotCommand(command="reset", description="reset"),
            BotCommand(command="log", description="log"),
        ]
    )


async def main() -> None:
    settings = Settings()  # type: ignore

    api = PRODUCTION

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        session=AiohttpSession(api=api),
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    storage = RedisStorage(
        redis=await settings.redis_dsn(),
        key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
        json_loads=msgspec.json.decode,
        json_dumps=partial(lambda obj: str(msgspec.json.encode(obj), encoding="utf-8")),
    )

    dp = Dispatcher(
        storage=storage,
        events_isolation=SimpleEventIsolation(),
        settings=settings,
        redis=storage.redis,
        developer_id=settings.developer_id,
    )
    dp.include_routers(handlers.router, errors.router)
    dp.startup.register(startup)
    dp.shutdown.register(shutdown)
    await set_default_commands(bot)
    # asyncio.create_task(start_scheduler())
    # dp.workflow_data.update({"scheduler": scheduler})

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        uvloop = __import__("uvloop")
        loop_factory = uvloop.new_event_loop

    except ModuleNotFoundError:
        loop_factory = asyncio.new_event_loop
        logger.info("uvloop not found, using default event loop")

    try:
        with asyncio.Runner(loop_factory=loop_factory) as runner:
            runner.run(main())

    except (CancelledError, KeyboardInterrupt):
        __import__("sys").exit(0)
