from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Bot as UserBot
from bot.db.models import UserAnalyzed, UserManager

if TYPE_CHECKING:
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)
path_to_folder = "sessions"


@router.message(Command(commands="stat"))
async def stat_cmd(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    r = await session.execute(
        select(UserAnalyzed).where(
            and_(
                UserAnalyzed.sended.is_(False),
                UserAnalyzed.accepted,
            )
        )
    )
    users = r.scalars().all()
    bots_ids = set(user.bot_id for user in users)
    stat = []
    for bot_id in bots_ids:
        counter = 0
        for user_analyzed in users:
            if user_analyzed.bot_id == bot_id:
                counter += 1
        bot = await session.get(UserBot, bot_id)
        stat.append(f"{bot.name}[{bot.phone}] есть {counter} чел.")
    if not stat:
        await message.answer("Нет пользователей для статистики")
        return
    await message.answer("\n".join(stat))
