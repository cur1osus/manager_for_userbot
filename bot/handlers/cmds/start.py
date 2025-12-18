from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart

from bot.db.models import UserManager
from bot.keyboards.inline import ik_main_menu
from bot.utils import fn

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import Message
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession


router = Router()
logger = logging.getLogger(__name__)
path_to_folder = "sessions"


@router.message(CommandStart(deep_link=True))
async def start_cmd_with_deep_link(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    args = command.args.split() if command.args else []
    deep_link = args[0]
    if deep_link == "true":
        user_manager = UserManager(
            id_user=message.from_user.id,
            username=message.from_user.username,
        )
        session.add(user_manager)
        await session.commit()
        msg = await message.answer(
            "Hello, world!", reply_markup=await ik_main_menu(user)
        )
        await fn.set_general_message(state, msg)


@router.message(CommandStart(deep_link=False))
async def start_cmd(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    if user is None and message.from_user:
        full_name = message.from_user.full_name
        username = message.from_user.username or "none"
        logger.warning(f"Незнакомец пытается получить доступ {full_name} @{username}")
        return
    msg = await message.answer("Hello, world!", reply_markup=await ik_main_menu(user))
    await fn.set_general_message(state, msg)
