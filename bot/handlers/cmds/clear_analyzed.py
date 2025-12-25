from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import UserAnalyzed, UserManager
from bot.keyboards.inline import _CONFIRM_NO, _CONFIRM_YES, ik_confirm_clear_keyboard

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command(commands=["clear_analyzed"]))
async def confirm_clear_cmd(
    message: Message,
    redis: Redis,
    user: UserManager | None,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if user is None:
        logger.warning(
            "Попытка очистить UserAnalyzed без доступа: %s", message.from_user
        )
        return

    records_count = await session.scalar(select(func.count(UserAnalyzed.id)))
    if not records_count:
        await message.answer("В таблице UserAnalyzed нет записей.")
        return

    await message.answer(
        f"Найдено {records_count} записей в UserAnalyzed. Очистить таблицу?",
        reply_markup=await ik_confirm_clear_keyboard(),
    )


@router.callback_query(F.data == _CONFIRM_YES)
async def clear_analyzed_yes(
    query: CallbackQuery,
    user: UserManager | None,
    session: AsyncSession,
) -> None:
    if user is None:
        logger.warning("Попытка очистить UserAnalyzed без доступа: %s", query.from_user)
        await query.answer("Нет доступа к действию.", show_alert=True)
        return
    if query.message is None:
        await query.answer("Сообщение недоступно.", show_alert=True)
        return

    records_count = await session.scalar(select(func.count(UserAnalyzed.id)))
    if not records_count:
        await query.message.edit_text("Таблица UserAnalyzed уже пустая.")
        await query.answer("Пусто.")
        return

    result = await session.execute(delete(UserAnalyzed))
    await session.commit()
    deleted_count = result.rowcount or records_count

    await query.message.edit_text(
        f"UserAnalyzed очищена. Удалено {deleted_count} записей."
    )
    await query.answer("Очистка выполнена.")


@router.callback_query(F.data == _CONFIRM_NO)
async def clear_analyzed_no(
    query: CallbackQuery,
    user: UserManager | None,
) -> None:
    if user is None:
        logger.warning("Попытка отменить очистку без доступа: %s", query.from_user)
        await query.answer("Нет доступа к действию.", show_alert=True)
        return
    if query.message:
        await query.message.edit_text("Очистка UserAnalyzed отменена.")
    await query.answer("Действие отменено.")
