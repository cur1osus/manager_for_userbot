from __future__ import annotations

import logging
import os
import shutil
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery

from bot.db.models import UserManager
from bot.keyboards.inline import ik_confirm_clear_keyboard

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)

_SESSIONS_DIR = "sessions"
_CONFIRM_DELETE_SESSIONS_YES = "delete_sessions_yes"
_CONFIRM_DELETE_SESSIONS_NO = "delete_sessions_no"


@router.message(Command(commands=["delete_sessions"]))
async def delete_sessions_cmd(
    message: Message,
    redis: Redis,
    user: UserManager | None,
    state: FSMContext,
) -> None:
    if user is None:
        logger.warning(
            "Попытка удалить папку sessions без доступа: %s", message.from_user
        )
        return

    if not os.path.exists(_SESSIONS_DIR):
        await message.answer("Папка sessions не найдена.")
        return

    try:
        items = os.listdir(_SESSIONS_DIR)
        if not items:
            await message.answer("Папка sessions пуста.")
            return

        await message.answer(
            f"В папке sessions найдено {len(items)} элементов. "
            "Вы уверены, что хотите удалить ВСЮ папку sessions? "
            "Это удалит все сессии и логи!",
            reply_markup=await ik_confirm_clear_keyboard(
                yes_callback=_CONFIRM_DELETE_SESSIONS_YES,
                no_callback=_CONFIRM_DELETE_SESSIONS_NO,
            ),
        )
        await state.update_data(delete_sessions_confirm=True)
    except Exception as e:
        logger.error("Ошибка при проверке папки sessions: %s", e)
        await message.answer("Ошибка при проверке папки sessions.")


@router.callback_query(F.data == _CONFIRM_DELETE_SESSIONS_YES)
async def delete_sessions_yes(
    query: CallbackQuery,
    user: UserManager | None,
    state: FSMContext,
) -> None:
    if user is None:
        logger.warning(
            "Попытка удалить папку sessions без доступа: %s", query.from_user
        )
        await query.answer("Нет доступа к действию.", show_alert=True)
        return
    if query.message is None:
        await query.answer("Сообщение недоступно.", show_alert=True)
        return

    data = await state.get_data()
    if not data.get("delete_sessions_confirm"):
        await query.answer("Сессия подтверждения истекла.", show_alert=True)
        return

    if not os.path.exists(_SESSIONS_DIR):
        await query.message.edit_text("Папка sessions не найдена.")
        await query.answer("Папка не найдена.")
        await state.update_data(delete_sessions_confirm=False)
        return

    try:
        shutil.rmtree(_SESSIONS_DIR)
        await query.message.edit_text("Папка sessions успешно удалена.")
        await query.answer("Удаление выполнено.")
        logger.info("Папка sessions удалена пользователем %s", query.from_user.id)
    except Exception as e:
        logger.error("Ошибка при удалении папки sessions: %s", e)
        await query.message.edit_text("Ошибка при удалении папки sessions.")
        await query.answer("Ошибка удаления.", show_alert=True)
    finally:
        await state.update_data(delete_sessions_confirm=False)


@router.callback_query(F.data == _CONFIRM_DELETE_SESSIONS_NO)
async def delete_sessions_no(
    query: CallbackQuery,
    user: UserManager | None,
    state: FSMContext,
) -> None:
    if user is None:
        logger.warning(
            "Попытка отменить удаление sessions без доступа: %s", query.from_user
        )
        await query.answer("Нет доступа к действию.", show_alert=True)
        return
    if query.message:
        await query.message.edit_text("Удаление папки sessions отменено.")
    await query.answer("Действие отменено.")
    await state.update_data(delete_sessions_confirm=False)
