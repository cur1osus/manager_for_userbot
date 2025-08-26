import asyncio
import logging

import msgpack
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm.session import sessionmaker

from bot.db.mysql import UserAnalyzed, UserBot, UserManager
from bot.utils import fn
from redis.asyncio import Redis

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
