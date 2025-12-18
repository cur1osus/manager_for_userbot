from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import any_state
from aiogram.types import CallbackQuery
from aiogram.types.reply_keyboard_remove import ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Bot, BotFolder, Job, JobName, UserManager
from bot.keyboards.factories import BotAddFactory
from bot.keyboards.inline import ik_main_menu
from bot.keyboards.reply import rk_cancel
from bot.settings import se
from bot.states import UserState
from bot.utils import fn

if TYPE_CHECKING:
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


async def _start_bot_registration(
    query: CallbackQuery,
    state: FSMContext,
    folder_id: int | None,
) -> None:
    await state.update_data(new_bot_folder_id=folder_id, save_bot=True)
    await query.message.delete()
    await query.message.answer("Введите api_id", reply_markup=await rk_cancel())
    await state.set_state(UserState.enter_api_id)


@router.message(any_state, F.text == "Отмена")
async def cancel_reg(
    message: Message,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    user: UserManager,
) -> None:
    await fn.state_clear(state)
    await message.answer("Добавление бота отменено", reply_markup=ReplyKeyboardRemove())
    msg = await message.answer("Главное меню", reply_markup=await ik_main_menu(user))
    await fn.set_general_message(state, msg)


@router.callback_query(F.data == "add_new_bot")
async def process_add_new_bot(
    query: CallbackQuery, user: UserManager, redis: Redis, state: FSMContext
) -> None:
    await _start_bot_registration(query, state, folder_id=None)


@router.callback_query(BotAddFactory.filter())
async def process_add_new_bot_in_folder(
    query: CallbackQuery,
    callback_data: BotAddFactory,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
) -> None:
    folder_id = callback_data.folder_id or None
    await _start_bot_registration(query, state, folder_id=folder_id)


@router.message(UserState.enter_api_id)
async def process_enter_api_id(
    message: Message, redis: Redis, state: FSMContext
) -> None:
    await state.update_data(api_id=message.text)
    await message.answer("Введите api_hash", reply_markup=None)
    await state.set_state(UserState.enter_api_hash)


@router.message(UserState.enter_api_hash)
async def process_enter_api_hash(
    message: Message, redis: Redis, state: FSMContext
) -> None:
    await state.update_data(api_hash=message.text)
    await message.answer("Введите phone", reply_markup=None)
    await state.set_state(UserState.enter_phone)


@router.message(UserState.enter_phone)
async def process_enter_phone(
    message: Message, redis: Redis, state: FSMContext
) -> None:
    if not message.text:
        return

    os.makedirs(se.path_to_folder, exist_ok=True)

    await state.update_data(phone=message.text)
    data = await state.get_data()
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")

    if not api_id or not api_hash:
        await message.answer(
            "Произошла ошибка, не обнаружено API ID или API HASH, нажмите 'Отмена' и попробуйте снова"
        )
        return

    relative_path = f"{se.path_to_folder}/{message.text}"
    path_session = os.path.abspath(f"{relative_path}.session")

    result = await fn.Telethon.send_code_via_telethon(
        message.text,
        int(api_id),
        api_hash,
        path_session,
    )

    if not result.success:
        await message.answer(str(result.message), reply_markup=None)
        return

    phone_code_hash = result.message
    await state.update_data(
        phone_code_hash=phone_code_hash,
        path_session=path_session,
    )
    await message.answer("Введите code", reply_markup=None)
    await state.set_state(UserState.enter_code)


@router.message(UserState.enter_code)
async def process_enter_code(
    message: Message,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
    user: UserManager,
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
    api_id_int = int(api_id)
    r = await fn.Telethon.create_telethon_session(
        phone,
        code,  # pyright: ignore
        api_id_int,
        api_hash,
        phone_code_hash,
        password,
        path_session,
    )
    if r.message == "password_required":
        await message.answer("Введите пароль", reply_markup=None)
        await state.update_data(code=message.text, is_password=True)
        return
    if not r.success:
        await message.answer(str(r.message), reply_markup=None)
        await fn.state_clear(state)
        return

    folder_name: str | None = None
    save_bot = data.get("save_bot", True)
    bot_id = data.get("bot_id")
    if save_bot:
        target_folder_id: int | None = None
        folder_id = data.get("new_bot_folder_id")
        if folder_id is not None:
            folder = await session.scalar(
                select(BotFolder).where(
                    BotFolder.id == folder_id,
                    BotFolder.user_manager_id == user.id,
                )
            )
            if folder:
                target_folder_id = folder.id
                folder_name = folder.name
            else:
                await message.answer("Папка не найдена, бот будет без папки")

        bot = Bot(
            api_id=api_id_int,
            api_hash=api_hash,
            phone=phone,
            path_session=path_session,
            is_connected=True,
            folder_id=target_folder_id,
        )
        job = Job(task=JobName.get_me_name.value)
        jobs = await bot.awaitable_attrs.jobs
        jobs.append(job)
        bots = await user.awaitable_attrs.bots
        bots.append(bot)
        session.add(bot)
        await session.commit()
    elif bot_id:
        bot = await user.get_obj_bot(bot_id)
        if not bot:
            await message.answer(
                "Бот не найден для обновления состояния",
                reply_markup=ReplyKeyboardRemove(),
            )
            await fn.state_clear(state)
            return
        bot.is_connected = True
        bot.path_session = path_session
        await session.commit()

    asyncio.create_task(fn.Manager.start_bot(phone, path_session, api_id_int, api_hash))
    status_text = "Бот подключен и запущен"
    if folder_name:
        status_text += f"\nПапка: {folder_name}"
    await message.answer(status_text, reply_markup=ReplyKeyboardRemove())
    await fn.state_clear(state)
    msg = await message.answer("Главное меню", reply_markup=await ik_main_menu(user))
    await fn.set_general_message(state, msg)
