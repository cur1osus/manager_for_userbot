from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.keyboards.factories import BackFactory
from bot.keyboards.inline import (
    ik_main_menu,
)
from bot.utils import fn

if TYPE_CHECKING:
    pass

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(BackFactory.filter(F.to == "default"))
async def back_default(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    await fn.state_clear(state)
    await query.message.edit_text("Главное меню", reply_markup=await ik_main_menu(user))
