from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio.session import AsyncSession

from bot.db.models import UserManager
from bot.keyboards.inline import ik_main_menu

if TYPE_CHECKING:
    pass

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "antiflood_mode")
async def antiflood_mode(
    query: CallbackQuery,
    user: UserManager,
    session: AsyncSession,
) -> None:
    user.is_antiflood_mode = not user.is_antiflood_mode
    await query.message.edit_reply_markup(reply_markup=await ik_main_menu(user))
    await session.commit()
