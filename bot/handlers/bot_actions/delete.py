from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Bot, UserManager
from bot.keyboards.inline import ik_main_menu
from bot.states.main import BotState
from bot.utils import fn

if TYPE_CHECKING:
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(BotState.main, F.data == "delete")
async def delete_bot_from_list(
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

    user.bots.remove(bot)
    await fn.Manager.stop_bot(phone=bot.phone, delete_session=True)
    await session.commit()
    await fn.state_clear(state)
    await query.message.edit_text("Бот удален", reply_markup=await ik_main_menu(user))
