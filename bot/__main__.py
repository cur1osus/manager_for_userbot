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
from sqlalchemy.orm.session import sessionmaker

from bot import handlers
from bot.background_tasks import (
    antiflood_pack_users,
    handle_job_from_userbot,
    send_not_accepted_posts,
)
from bot.db.base import close_db, create_db_session_pool, init_db
from bot.middlewares.throw_session import DBSessionMiddleware
from bot.middlewares.throw_user import ThrowUserMiddleware
from bot.scheduler import default_scheduler as scheduler
from bot.scheduler import logger as scheduler_logger
from bot.settings import Settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

scheduler_logger.setLevel(logging.ERROR)

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
    dispatcher.update.outer_middleware(DBSessionMiddleware(session_pool=db_session))
    dispatcher.update.outer_middleware(ThrowUserMiddleware())

    asyncio.create_task(
        start_scheduler(
            sessionmaker=db_session,  # pyright: ignore
            bot=bot,
            redis=redis,
        )
    )

    logger.info("Bot started")


async def shutdown(dispatcher: Dispatcher) -> None:
    await dispatcher["db_session_closer"]()
    logger.info("Bot stopped")


async def start_scheduler(sessionmaker: sessionmaker, bot: Bot, redis: Redis) -> None:
    scheduler.every(15).seconds.do(
        antiflood_pack_users,
        sessionmaker=sessionmaker,
        bot=bot,
        redis=redis,
    )
    scheduler.every(10).seconds.do(
        send_not_accepted_posts,
        sessionmaker=sessionmaker,
        bot=bot,
        redis=redis,
    )
    scheduler.every(5).seconds.do(
        handle_job_from_userbot,
        sessionmaker=sessionmaker,
        bot=bot,
    )
    while True:
        await scheduler.run_pending()
        await asyncio.sleep(1)


async def set_default_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="start"),
            BotCommand(command="stat", description="статистика"),
            BotCommand(command="ban", description="быстро добавить в бан"),
            BotCommand(command="reset", description="reset"),
            BotCommand(command="log", description="log"),
        ]
    )


async def main() -> None:
    settings = Settings()

    api = PRODUCTION

    bot = Bot(
        token=settings.bot_token,
        session=AiohttpSession(api=api),
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    redis = await settings.redis_dsn()
    storage = RedisStorage(
        redis=redis,
        key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
        json_loads=msgspec.json.decode,
        json_dumps=partial(lambda obj: str(msgspec.json.encode(obj), encoding="utf-8")),
    )

    dp = Dispatcher(
        storage=storage,
        events_isolation=SimpleEventIsolation(),
        settings=settings,
        redis=storage.redis,
    )

    dp.include_routers(handlers.router)
    dp.startup.register(startup)
    dp.shutdown.register(shutdown)
    await set_default_commands(bot)

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
