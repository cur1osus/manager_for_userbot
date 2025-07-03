from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.mysql.models import Bot, UserManager
from bot.states import UserState
from bot.utils import fn
from aiogram.utils.formatting import Code

if TYPE_CHECKING:
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)
path_to_folder = "sessions"


@router.message(UserState.action, Command(commands="log"))  # type: ignore
async def start_cmd_state(
    message: Message,
    redis: Redis,
    user: UserManager | None,
    state: FSMContext,
    command: CommandObject,
    sessionmaker: async_sessionmaker,
) -> None:
    bot_id = (await state.get_data()).get("bot_id")
    if not bot_id:
        await message.answer("Не выбран бот")
        return
    async with sessionmaker() as session:
        bot = await session.get(Bot, bot_id)
        phone = bot.phone
    path_log = os.path.join("sessions", f"{phone}_bot.log")
    args = command.args.split(" ") if command.args else []
    line_count = int(args[0]) if len(args) > 0 and args[0].isdigit() and len(args) < 2 else 20
    r = fn.get_log(path_log, line_count)
    if isinstance(r, str):
        await message.answer(r)
        return
    txt = Code("\n\n".join(r))
    if len(txt) > 4000:
        await message.answer("Слишком большой лог")
        return
    await message.answer(txt.as_html())


@router.message(Command(commands="log"))  # type: ignore
async def start_cmd(
    message: Message,
    redis: Redis,
    user: UserManager | None,
    state: FSMContext,
    command: CommandObject,
) -> None:
    args = command.args.split(" ") if command.args else []
    line_count = int(args[0]) if len(args) > 0 and args[0].isdigit() and len(args) < 2 else 20
    r = fn.get_log("nohup.out", line_count)
    if isinstance(r, str):
        await message.answer(r)
        return
    txt = Code("\n\n".join(r))
    if len(txt) > 4000:
        await message.answer("Слишком большой лог")
        return
    await message.answer(txt.as_html())
