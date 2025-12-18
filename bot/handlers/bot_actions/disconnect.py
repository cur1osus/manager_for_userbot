from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Bot, Job, UserManager
from bot.keyboards.inline import ik_main_menu
from bot.states.main import BotState
from bot.utils import fn

if TYPE_CHECKING:
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(BotState.main, F.data == "disconnected")
async def disconnected_bot(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    bot_id = data["bot_id"]
    bot: Bot | None = await user.get_obj_bot(bot_id)

    if not bot:
        await query.answer("Бот не найден")
        return

    bot.is_connected = False
    bot.is_started = False
    await fn.Manager.stop_bot(phone=bot.phone)
    await session.execute(delete(Job).where(Job.bot_id == bot.id))
    await session.commit()
    await query.message.edit_text("Бот отключен", reply_markup=await ik_main_menu(user))
