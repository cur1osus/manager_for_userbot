from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import BotFolder, UserManager
from bot.keyboards.factories import BackFactory
from bot.keyboards.inline import ik_bot_folder_list
from bot.states.main import BotState
from bot.utils import fn

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(BotState.main, BackFactory.filter(F.to == "bots"))
async def back(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    await fn.state_clear(state)
    folders = (
        await session.scalars(
            select(BotFolder)
            .where(BotFolder.user_manager_id == user.id)
            .order_by(BotFolder.id.asc())
        )
    ).all()
    await query.message.edit_text(
        text="Папки",
        reply_markup=await ik_bot_folder_list(list(folders)),
    )
