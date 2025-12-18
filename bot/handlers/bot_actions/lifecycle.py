from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Bot, UserManager
from bot.keyboards.inline import ik_action_with_bot
from bot.states.main import BotState

if TYPE_CHECKING:
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(BotState.main, F.data == "start")
async def start_bot_process(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    bot_id = data["bot_id"]
    back_to = data.get("bots_back_to", "bots_all")
    bot: Bot | None = await user.get_obj_bot(bot_id)
    if bot:
        bot.is_started = True
        await session.commit()
        await query.message.edit_text(
            "Бот Начал писать и анализировать сообщения 🟢",
            reply_markup=await ik_action_with_bot(back_to=back_to),
        )


@router.callback_query(BotState.main, F.data == "stop")
async def stop_bot_process(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    bot_id = data["bot_id"]
    back_to = data.get("bots_back_to", "bots_all")
    bot: Bot | None = await user.get_obj_bot(bot_id)
    if bot:
        bot.is_started = False
        await session.commit()
        await query.message.edit_text(
            "Бот остановлен и не будет писать и анализировать сообщения 🔴",
            reply_markup=await ik_action_with_bot(back_to=back_to),
        )
