from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import UserManager
from bot.keyboards.factories import BotFactory
from bot.keyboards.inline import ik_action_with_bot, ik_connect_bot
from bot.states.main import BotState

if TYPE_CHECKING:
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(BotFactory.filter())
async def manage_bot(
    query: CallbackQuery,
    callback_data: BotFactory,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = callback_data.id
    bot = await user.get_obj_bot(bot_id)
    if not bot:
        await query.answer("Бот не найден", show_alert=True)
        return

    data = await state.get_data()
    back_to = data.get("bots_back_to", "bots_all")

    if bot.is_connected:
        await query.message.edit_text(
            "Выберите действие",
            reply_markup=await ik_action_with_bot(back_to=back_to),
        )
    else:
        await query.message.edit_text(
            "Выберите действие",
            reply_markup=await ik_connect_bot(back_to=back_to),
        )
    await state.set_state(BotState.main)
    await state.update_data(bot_id=bot_id, bots_back_to=back_to)
