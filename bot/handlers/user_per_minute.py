from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import UserManager
from bot.keyboards.factories import UserPerMinuteFactory
from bot.keyboards.inline import ik_num_matrix_users

if TYPE_CHECKING:
    pass

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "users_per_minute")
async def users_per_minute(
    query: CallbackQuery,
    user: UserManager,
) -> None:
    try:
        await query.message.edit_text(
            text="Выбери пропускную способность:",
            reply_markup=await ik_num_matrix_users(user.users_per_minute),
        )
    except Exception:
        logger.exception("not modified message")


@router.callback_query(UserPerMinuteFactory.filter())
async def change_users_per_minute(
    query: CallbackQuery,
    callback_data: UserPerMinuteFactory,
    user: UserManager,
    session: AsyncSession,
) -> None:
    upm = callback_data.value
    user.users_per_minute = upm
    user = await session.merge(user)
    await session.commit()
    try:
        await users_per_minute(query, user)
    except Exception:
        logger.exception("not modified message")
