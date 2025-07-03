from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.db.mysql.models import UserManager

if TYPE_CHECKING:
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)
path_to_folder = "sessions"


@router.message(Command(commands="reset"))
async def start_cmd(
    message: Message,
    redis: Redis,
    user: UserManager | None,
    state: FSMContext,
) -> None:
    await state.clear()
    await message.answer("Состояние сброшено")
