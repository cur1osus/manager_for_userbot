from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.mysql.models import (
    Bot,
    Job,
    UserManager,
)
from bot.keyboards.factories import BackFactory, BotFactory
from bot.keyboards.inline import (
    ik_action_with_bot,
    ik_available_bots,
    ik_connect_bot,
    ik_main_menu,
)
from bot.states.main import BotState, UserState
from bot.utils import fn

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
    state: FSMContext,
    session: AsyncSession,
    user: UserManager,
) -> None:
    bot_id = (await state.get_data()).get("bot_id")

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
            reply_markup=await ik_action_with_bot(back_to="bots"),
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
    await fn.Manager.stop_bot(phone=bot.phone)
    await session.execute(delete(Job).where(Job.bot_id == bot.id))
    await session.commit()
    await query.message.edit_text("Бот отключен", reply_markup=await ik_main_menu(user))


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
    await fn.Manager.stop_bot(phone=bot.phone, delete_session=True)
    await session.commit()
    await fn.state_clear(state)
    await query.message.edit_text("Бот удален", reply_markup=await ik_main_menu(user))


@router.callback_query(BotState.main, BackFactory.filter(F.to == "bots"))
async def back(
    query: CallbackQuery,
    state: FSMContext,
    user: UserManager,
) -> None:
    await query.message.edit_text(
        "Боты", reply_markup=await ik_available_bots(user.bots)
    )
