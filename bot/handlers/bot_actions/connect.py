from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import BotFolder, UserManager
from bot.keyboards.factories import BackFactory, BotMoveToFolderFactory
from bot.keyboards.inline import (
    ik_action_with_bot,
    ik_connect_bot,
    ik_move_bot_folders,
)
from bot.states.main import BotState, UserState
from bot.utils import fn
from bot.handlers import bots as bots_handlers

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(BotState.main, F.data == "connect")
async def connect_bot(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: UserManager,
) -> None:
    data = await state.get_data()
    bot_id = data.get("bot_id")
    back_to = data.get("bots_back_to", "bots_all")

    if not bot_id:
        await query.message.edit_text(text="bot_id пустой")
        return

    bot = await user.get_obj_bot(bot_id)
    if not bot:
        await query.message.edit_text(text="Бот не найден")
        return

    await fn.Manager.start_bot(
        bot.phone,
        bot.path_session,
        bot.api_id,
        bot.api_hash,
    )
    await query.message.edit_text(
        "Пытаемся подключить Бота с уже существующей сессией..."
    )

    await asyncio.sleep(2)
    if await fn.Manager.bot_run(bot.phone):
        bot.is_connected = True
        await session.commit()
        await query.message.edit_text(
            "Бот успешно подключен!",
            reply_markup=await ik_action_with_bot(back_to=back_to),
        )
        return

    result = await fn.Telethon.send_code_via_telethon(
        bot.phone,
        bot.api_id,
        bot.api_hash,
        bot.path_session,
    )
    if result.success:
        await query.message.edit_text(
            "К сожалению, Бот не смог подключиться по старой сессии, "
            "поэтому мы отправили код, как получите его отправьте мне",
        )
    else:
        await query.message.answer(f"Ошибка при отправке кода: {result.message}")
        return

    await state.update_data(
        bot_id=bot.id,
        api_id=bot.api_id,
        api_hash=bot.api_hash,
        phone=bot.phone,
        phone_code_hash=result.message,
        path_session=bot.path_session,
        save_bot=False,
    )
    await state.set_state(UserState.enter_code)


@router.callback_query(BotState.main, F.data == "move_bot_folder")
async def choose_folder_for_bot(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: UserManager,
) -> None:
    data = await state.get_data()
    bot_id = data.get("bot_id")
    if not bot_id:
        await query.answer("Бот не найден", show_alert=True)
        return

    bot = await user.get_obj_bot(bot_id)
    if not bot:
        await query.answer("Бот не найден", show_alert=True)
        return

    folders = (
        await session.scalars(
            select(BotFolder)
            .where(BotFolder.user_manager_id == user.id)
            .order_by(BotFolder.id.asc())
        )
    ).all()

    await query.message.edit_text(
        text="Выберите папку для бота",
        reply_markup=await ik_move_bot_folders(
            list(folders), bot.folder_id, back_to="bot_actions"
        ),
    )


@router.callback_query(BotState.main, BotMoveToFolderFactory.filter())
async def move_bot_to_folder(
    query: CallbackQuery,
    callback_data: BotMoveToFolderFactory,
    state: FSMContext,
    session: AsyncSession,
    user: UserManager,
) -> None:
    data = await state.get_data()
    bot_id = data.get("bot_id")
    if not bot_id:
        await query.answer("Бот не найден", show_alert=True)
        return

    bot = await user.get_obj_bot(bot_id)
    if not bot:
        await query.answer("Бот не найден", show_alert=True)
        return

    old_folder_id = bot.folder_id
    target_folder_id = callback_data.id
    if target_folder_id == 0:
        bot.folder_id = None
        folder_name = "без папки"
    else:
        folder = await session.scalar(
            select(BotFolder).where(
                BotFolder.id == target_folder_id,
                BotFolder.user_manager_id == user.id,
            )
        )
        if not folder:
            await query.answer("Папка не найдена", show_alert=True)
            return
        bot.folder_id = folder.id
        folder_name = folder.name

    await session.commit()

    await query.answer(text=f"Бот перемещен в '{folder_name}'", show_alert=True)
    await _show_previous_folder(
        query,
        session,
        state,
        user,
        old_folder_id=old_folder_id,
    )


@router.callback_query(BotState.main, BackFactory.filter(F.to == "bot_actions"))
async def back_to_bot_actions_menu(
    query: CallbackQuery,
    state: FSMContext,
    user: UserManager,
) -> None:
    data = await state.get_data()
    back_to = data.get("bots_back_to", "bots_all")
    bot_id = data.get("bot_id")
    bot = await user.get_obj_bot(bot_id) if bot_id else None
    markup = (
        await ik_action_with_bot(back_to=back_to)
        if bot and bot.is_connected
        else await ik_connect_bot(back_to=back_to)
    )

    await query.message.edit_text(
        "Выберите действие",
        reply_markup=markup,
    )


async def _show_previous_folder(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
    *,
    old_folder_id: int | None,
) -> None:
    if old_folder_id:
        folder = await session.scalar(
            select(BotFolder).where(
                BotFolder.id == old_folder_id,
                BotFolder.user_manager_id == user.id,
            )
        )
        if folder:
            await bots_handlers.show_folder_bots_by_id(
                query,
                session,
                state,
                user,
                folder_id=folder.id,
            )
            return

    await bots_handlers.show_no_folder_bots(query, session, state, user)
