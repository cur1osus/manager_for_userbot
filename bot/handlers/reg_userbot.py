from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import any_state
from aiogram.types import CallbackQuery
from aiogram.types.reply_keyboard_remove import ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.mysql.models import Bot, Job, JobName, UserManager
from bot.keyboards.inline import ik_main_menu
from bot.keyboards.reply import rk_cancel
from bot.states import UserState
from bot.utils import fn
from bot.utils.manager import start_bot

if TYPE_CHECKING:
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)
path_to_folder = "sessions"


@router.message(any_state, F.text == "Отмена")
async def cancel_reg(message: Message, redis: Redis, state: FSMContext, sessionmaker: async_sessionmaker) -> None:
    await state.clear()
    await message.answer("Добавление бота отменено", reply_markup=ReplyKeyboardRemove())
    msg = await message.answer("Главное меню", reply_markup=await ik_main_menu())
    await fn.set_general_message(state, msg)


@router.callback_query(F.data == "add_new_bot")
async def process_add_new_bot(query: CallbackQuery, user: UserManager, redis: Redis, state: FSMContext) -> None:
    await query.message.delete()
    await query.message.answer("Введите api_id", reply_markup=await rk_cancel())
    await state.set_state(UserState.enter_api_id)


@router.message(UserState.enter_api_id)
async def process_enter_api_id(message: Message, redis: Redis, state: FSMContext) -> None:
    await state.update_data(api_id=message.text)
    await message.answer("Введите api_hash", reply_markup=None)
    await state.set_state(UserState.enter_api_hash)


@router.message(UserState.enter_api_hash)
async def process_enter_api_hash(message: Message, redis: Redis, state: FSMContext) -> None:
    await state.update_data(api_hash=message.text)
    await message.answer("Введите phone", reply_markup=None)
    await state.set_state(UserState.enter_phone)


@router.message(UserState.enter_phone)
async def process_enter_phone(message: Message, redis: Redis, state: FSMContext) -> None:
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
    )
    await message.answer("Введите code", reply_markup=None)
    await state.set_state(UserState.enter_code)


@router.message(UserState.enter_code)
async def process_enter_code(
    message: Message, redis: Redis, state: FSMContext, session: AsyncSession, user: UserManager
) -> None:
    data = await state.get_data()

    is_password = data.get("is_password", False)
    code = data["code"] if is_password else message.text
    password = message.text if is_password else None

    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]
    path_session = data["path_session"]
    if not message.text:
        return
    r = await fn.create_telethon_session(
        phone,
        code,
        int(api_id),
        api_hash,
        phone_code_hash,
        password,
        path_session,
    )
    if r.message == "password":
        await message.answer("Введите пароль", reply_markup=None)
        await state.update_data(code=message.text, is_password=True)
        return
    elif r.message == "error":
        await message.answer("Ошибка при создании сессии", reply_markup=None)
        await state.clear()
        return

    if data.get("save_bot", True):
        bot = Bot(
            api_id=int(api_id),
            api_hash=api_hash,
            phone=phone,
            path_session=path_session,
            is_connected=True,
        )
        job = Job(task=JobName.get_me_name.value)
        bot.jobs.append(job)
        bots = await user.awaitable_attrs.bots
        bots.append(bot)
        session.add(bot)
        await session.commit()

    await start_bot(phone, path_to_folder)
    await message.answer("Бот подключен и запущен", reply_markup=ReplyKeyboardRemove())
    await state.clear()
    msg = await message.answer("Главное меню", reply_markup=await ik_main_menu())
    await fn.set_general_message(state, msg)
