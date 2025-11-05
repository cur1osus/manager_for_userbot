import asyncio
import logging

import msgpack
from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.session import sessionmaker

from bot.db.mysql import UserAnalyzed, UserBot, UserManager
from bot.db.mysql.models import Job
from bot.utils import fn

logger = logging.getLogger(__name__)


def key_builder(key: str) -> str:
    return f"fsm:0:0:0:default:{key}"


key = key_builder("last_id")


async def job_sec(sessionmaker: sessionmaker, bot: Bot, redis: Redis):
    async with sessionmaker() as session:
        users = await session.scalars(
            select(UserAnalyzed)
            .where(UserAnalyzed.accepted.is_(False))
            .order_by(UserAnalyzed.id.desc())
            .limit(30),
        )
        users = users.all()

        if not users:
            return

        last_id = await redis.get(key)
        if last_id:
            last_id = int(last_id)
        new_users = (
            [user for user in users if user.id > last_id]
            if last_id or last_id == 0
            else [users[0]]
        )

        if not new_users:
            return

        new_last_id: int = max(user.id for user in new_users)
        await redis.set(key, new_last_id)

        for user in new_users:
            user: UserAnalyzed

            d: dict = msgpack.unpackb(user.decision)

            userbot: UserBot = await user.awaitable_attrs.bot
            manager: UserManager = await userbot.awaitable_attrs.manager

            if d.get("banned"):
                continue
            raw_msg = user.additional_message
            t = await fn.short_view(user.id, userbot.name, d, raw_msg)

            await asyncio.sleep(1)
            try:
                await bot.send_message(
                    manager.id_user,
                    text=t,
                    disable_notification=True,
                )
            except:
                pass
            await bot.send_message(474701274, text=t)


async def handle_job(sessionmaker: async_sessionmaker[AsyncSession], bot: Bot):
    async with sessionmaker() as session:
        jobs = await session.scalars(select(Job).where(Job.answer.is_(None)))
        jobs = jobs.all()

        if not jobs:
            return

        for job in jobs:
            userbot = await session.get(UserBot, job.bot_id)
            if not userbot:
                logger.info(f"UserBot не найден по id {job.id}")
                job.answer = msgpack.packb(True)
                continue
            manager = await userbot.awaitable_attrs.manager
            try:
                match job.task:
                    case "delete_private_channel":
                        channel = msgpack.unpackb(job.task_metadata)
                        await bot.send_message(
                            chat_id=manager.id_user,
                            text=f"Удалите канал ({channel}), так как вы были в нем забанены или удалены, это затормаживает корректную работу бота",
                        )
                    case "connection_error":
                        await bot.send_message(
                            chat_id=manager.id_user,
                            text=f"Ошибка подключения к серверу для бота {userbot.name}[{userbot.phone}]",
                        )
                    case "flood_wait_error":
                        userbot.is_started = False
                        data: dict = msgpack.unpackb(job.task_metadata)
                        time = (
                            f"{data['time'] // 3600} ч."
                            if data["time"] > 3600
                            else f"{data['time']} сек."
                        )
                        await bot.send_message(
                            chat_id=manager.id_user,
                            text=f"Ошибка FloodWait(время окончания: {time}) для {userbot.name}[{userbot.phone}], бот был остановлен",
                        )
            except Exception as e:
                logger.error(f"Ошибка при обработке задания {job.id}: {e}")
            job.answer = msgpack.packb(True)
        await session.commit()
