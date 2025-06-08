from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart

from bot.db.sqlite.models import UserManager
from bot.keyboards.inline import ik_main_menu

if TYPE_CHECKING:
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)
path_to_folder = "sessions"


@router.message(CommandStart(deep_link=True))
async def start_cmd_with_deep_link(
    msg: Message,
    command: CommandObject,
    redis: Redis,
) -> None:
    args = command.args.split() if command.args else []
    deep_link = args[0]

    logger.info(args)


@router.message(CommandStart(deep_link=False))
async def start_cmd(message: Message, redis: Redis, user: UserManager | None) -> None:
    if user is None and message.from_user:
        full_name = message.from_user.full_name
        username = message.from_user.username or "none"
        logger.warning(f"Незнакомец пытается получить доступ {full_name} @{username}")
        return
    await message.answer("Hello, world!", reply_markup=await ik_main_menu())
