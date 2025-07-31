from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.mysql.models import (
    Bot,
    UserManager,
)
from bot.keyboards.factories import BackFactory, BotFactory
from bot.keyboards.inline import (
    ik_action_with_bot,
    ik_available_bots,
    ik_main_menu,
    ik_connect_bot,
)
from bot.states import UserState
from bot.states.main import BotState
from bot.utils import fn
from bot.utils.manager import delete_bot
from config import path_to_folder

if TYPE_CHECKING:
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(BotFactory.filter())
async def manage_bot(
    query: CallbackQuery,
    callback_data: BotFactory,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = callback_data.id
    bot = await user.get_obj_bot(bot_id)

    if bot.is_connected:
        await query.message.edit_text(
            "Выберите действие",
            reply_markup=await ik_action_with_bot(back_to="bots"),
        )
    else:
        await query.message.edit_text(
            "Выберите действие",
            reply_markup=await ik_connect_bot(back_to="bots"),
        )
    await state.set_state(BotState.main)
    await state.update_data(bot_id=bot_id)


@router.callback_query(BotState.main, F.data == "connect")
async def connect_bot(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = (await state.get_data()).get("bot_id")

    if not bot_id:
        await query.message.edit_text(text="bot_id пустой")
        return

    bot = await user.get_obj_bot(bot_id)
    phone_code_hash = await fn.send_code_via_telethon(
        bot.phone,
        bot.api_id,
        bot.api_hash,
        bot.path_session,
    )
    if not phone_code_hash:
        await query.message.answer("Ошибка при отправке кода", reply_markup=None)
        return

    await state.set_state(UserState.enter_code)
    await state.update_data(
        api_id=bot.api_id,
        api_hash=bot.api_hash,
        phone=bot.phone,
        phone_code_hash=phone_code_hash,
        path_session=bot.path_session,
        save_bot=False,
    )

    await query.message.edit_text("Введите code", reply_markup=None)


@router.callback_query(BotState.main, F.data == "start")
async def start_bot_process(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = (await state.get_data())["bot_id"]
    bot: Bot | None = await user.get_obj_bot(bot_id)
    if bot:
        bot.is_started = True
        await session.commit()
        await query.message.edit_text(
            "Бот Начал писать и анализировать сообщения 🟢",
            reply_markup=await ik_action_with_bot(),
        )


@router.callback_query(BotState.main, F.data == "stop")
async def stop_bot_process(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = (await state.get_data())["bot_id"]
    bot: Bot | None = await user.get_obj_bot(bot_id)
    if bot:
        bot.is_started = False
        await session.commit()
        await query.message.edit_text(
            "Бот остановлен и не будет писать и анализировать сообщения 🔴",
            reply_markup=await ik_action_with_bot(),
        )


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
    await delete_bot(phone=bot.phone, path_to_folder=path_to_folder)
    await session.commit()
    await query.message.edit_text("Бот отключен", reply_markup=await ik_main_menu())


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
    await delete_bot(phone=bot.phone, path_to_folder=path_to_folder)
    await session.commit()
    await fn.state_clear(state)
    await query.message.edit_text("Бот удален", reply_markup=await ik_main_menu())


@router.callback_query(BotState.main, BackFactory.filter(F.to == "bots"))
async def back(
    query: CallbackQuery,
    state: FSMContext,
    user: UserManager,
) -> None:
    await query.message.edit_text(
        "Боты", reply_markup=await ik_available_bots(user.bots)
    )
