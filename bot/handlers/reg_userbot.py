from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.keyboards.reply import rk_cancel
from bot.keyboards.inline import ik_main_menu
from bot.db.mysql.models import Bot
from bot.states import UserState
from bot.utils.func import Function as fn
from bot.utils.manager import start_bot
from aiogram.fsm.state import any_state
from aiogram.types.reply_keyboard_remove import ReplyKeyboardRemove

if TYPE_CHECKING:
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)
path_to_folder = "sessions"


@router.message(any_state, F.text == "Отмена")
async def cancel_reg(
    message: Message, redis: Redis, state: FSMContext, sessionmaker: async_sessionmaker
):
    await state.clear()
    await message.answer("Добавление бота отменено", reply_markup=ReplyKeyboardRemove())
    await message.answer("Главное меню", reply_markup=await ik_main_menu())


@router.callback_query(F.data == "add_new_bot")
async def process_add_new_bot(query: CallbackQuery, redis: Redis, state: FSMContext):
    if not query.message or isinstance(query.message, InaccessibleMessage):
        return
    await query.message.delete()
    await query.message.answer("Введите api_id", reply_markup=await rk_cancel())
    await state.set_state(UserState.enter_api_id)


@router.message(UserState.enter_api_id)
async def process_enter_api_id(message: Message, redis: Redis, state: FSMContext):
    await state.update_data(api_id=message.text)
    await message.answer("Введите api_hash", reply_markup=None)
    await state.set_state(UserState.enter_api_hash)


@router.message(UserState.enter_api_hash)
async def process_enter_api_hash(message: Message, redis: Redis, state: FSMContext):
    await state.update_data(api_hash=message.text)
    await message.answer("Введите phone", reply_markup=None)
    await state.set_state(UserState.enter_phone)


@router.message(UserState.enter_phone)
async def process_enter_phone(message: Message, redis: Redis, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()
    api_id = data["api_id"]
    api_hash = data["api_hash"]
    if not message.text:
        return
    if not os.path.exists(path_to_folder):
        os.makedirs(path_to_folder)

    # Получаем абсолютный путь
    session_name = f"{path_to_folder}/{message.text}_session"
    absolute_path = os.path.abspath(f"{session_name}.session")

    path_session = absolute_path
    phone_code_hash = await fn.send_code_via_telethon(
        message.text,
        int(api_id),
        api_hash,
        path_session,
    )
    if phone_code_hash is None:
        await message.answer("Ошибка при отправке кода", reply_markup=None)
        return
    await state.update_data(
        phone_code_hash=phone_code_hash,
        path_session=path_session,
        path_to_folder=path_to_folder,
    )
    await message.answer("Введите code", reply_markup=None)
    await state.set_state(UserState.enter_code)


@router.message(UserState.enter_code)
async def process_enter_code(
    message: Message, redis: Redis, state: FSMContext, sessionmaker: async_sessionmaker
):
    data = await state.get_data()
    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]
    path_session = data["path_session"]
    if not message.text:
        return
    r = await fn.create_telethon_session(
        phone,
        message.text,
        int(api_id),
        api_hash,
        phone_code_hash,
        None,
        path_session,
    )
    if r.message == "password":
        await message.answer("Введите пароль", reply_markup=None)
        await state.set_state(UserState.enter_password)
        return

    async with sessionmaker() as session:
        session.add(
            Bot(
                api_id=int(api_id),
                api_hash=api_hash,
                phone=phone,
                path_session=path_session,
            )
        )
        await session.commit()
    await message.answer("Готово", reply_markup=None)
    await state.clear()


@router.message(UserState.enter_password)
async def process_enter_password(
    message: Message, redis: Redis, state: FSMContext, sessionmaker: async_sessionmaker
):
    data = await state.get_data()
    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]
    path_session = data["path_session"]
    if not message.text:
        return
    r = await fn.create_telethon_session(
        phone,
        message.text,
        int(api_id),
        api_hash,
        phone_code_hash,
        message.text,
        path_session,
    )
    if r.message == "error":
        await message.answer("Ошибка при создании сессии", reply_markup=None)
        await state.clear()
        return
    if r.message == "password":
        await message.answer("Введите пароль", reply_markup=None)
        return

    async with sessionmaker() as session:
        session.add(
            Bot(
                api_id=int(api_id),
                api_hash=api_hash,
                phone=phone,
                path_session=path_session,
            )
        )
        await session.commit()
    await start_bot(phone, path_to_folder)
    await message.answer("Бот подключен и запущен", reply_markup=ReplyKeyboardRemove())
    await state.clear()
