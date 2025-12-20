from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from bot.db.models import UserManager
from bot.keyboards.inline import ik_cancel_action
from bot.states.main import InfoState
from bot.utils import fn

if TYPE_CHECKING:
    from aiogram.types import Message


router = Router()
logger = logging.getLogger(__name__)


@router.message(Command(commands=["ban"]))
async def add_banned_users(
    message: Message,
    state: FSMContext,
    user: UserManager,
) -> None:
    if user is None:
        logger.warning("Попытка добавить в бан без доступа: %s", message.from_user)
        return

    await fn.state_clear(state)

    banned_users = await user.awaitable_attrs.banned_users
    all_page = await fn.count_page(len_data=len(banned_users), q_string_per_page=10)
    current_page = all_page

    await state.update_data(
        type_data="ban",
        current_page=current_page,
        all_page=all_page,
    )

    await message.answer(
        "Введите username(-s)", reply_markup=await ik_cancel_action()
    )
    await state.set_state(InfoState.add)
