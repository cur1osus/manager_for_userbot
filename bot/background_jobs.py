import asyncio
import logging

import msgpack
from aiogram import Bot
from cachetools import TTLCache
from sqlalchemy import select
from sqlalchemy.orm.session import sessionmaker
import html

from bot.db.mysql import UserAnalyzed

cache = TTLCache(maxsize=1, ttl=5000)

logger = logging.getLogger(__name__)


async def job_sec(sessionmaker: sessionmaker, bot: Bot):
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

    last_id = cache.get("last_id", None)
    new_users = [user for user in users if user.id > last_id] if last_id else [users[0]]

    if not new_users:
        return

    new_last_id = max(user.id for user in new_users)
    cache["last_id"] = new_last_id

    for user in new_users:
        user: UserAnalyzed
        try:
            text = msgpack.unpackb(user.decision)
        except:
            text = "не смог распаковать"
        await asyncio.sleep(1)
        await bot.send_message(chat_id=474701274, text=user.additional_message)
        await bot.send_message(chat_id=474701274, text=html.escape(str(text)))
