from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Bot, Job, UserManager
from bot.handlers import bots as bots_handlers
from bot.handlers.bots import FOLDER_BACK_PREFIX
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

    back_to = data.get("bots_back_to", "bots_all")
    if back_to == "bots_all":
        await bots_handlers.show_all_bots(query, session, state, user)
    elif back_to == "bots_no_folder":
        await bots_handlers.show_no_folder_bots(query, session, state, user)
    elif isinstance(back_to, str) and back_to.startswith(FOLDER_BACK_PREFIX):
        with contextlib.suppress(Exception):
            folder_id = int(back_to.removeprefix(FOLDER_BACK_PREFIX))
            await bots_handlers.show_folder_bots_by_id(
                query,
                session,
                state,
                user,
                folder_id=folder_id,
            )
            return
        await bots_handlers.show_all_bots(query, session, state, user)
    else:
        await query.message.edit_text("Бот отключен", reply_markup=await ik_main_menu(user))
