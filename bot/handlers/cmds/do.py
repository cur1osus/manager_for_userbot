from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.types.reply_keyboard_remove import ReplyKeyboardRemove
from aiogram.utils.media_group import MediaGroupBuilder

from bot.db.models import UserManager
from bot.keyboards.inline import ik_main_menu
from bot.keyboards.reply import rk_cancel
from bot.states.main import UserState
from bot.utils import fn
from bot.utils.process_d import (
    clear_dirs_d,
    get_paths,
    process_image_d_v1,
    process_image_d_v2,
    process_image_d_vertical,
)

if TYPE_CHECKING:
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command(commands="do"))
async def do_cmd(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    m = await message.answer("Жду файлы", reply_markup=await rk_cancel())
    await fn.set_general_message(state, m)
    await fn.state_clear(state)
    await state.set_state(UserState.send_files_do)


@router.message(UserState.send_files_do, F.text == "Отмена")
async def cancel(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    await fn.state_clear(state)
    await message.answer("Отменено", reply_markup=ReplyKeyboardRemove())
    msg = await message.answer("Hello, world!", reply_markup=await ik_main_menu(user))
    await fn.set_general_message(state, msg)


@router.message(UserState.send_files_do, F.document)
async def send_files_do(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    await message.bot.download(
        message.document.file_id,
        os.path.join("images_d", f"{message.document.file_name}"),
    )
    await message.answer(f"Файл {message.document.file_name} сохранен")


@router.message(UserState.send_files_do)
async def do_end(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    await fn.state_clear(state)

    text = message.text
    func = None

    match text:
        case "w":
            func = process_image_d_v1
        case "b":
            func = process_image_d_v2
        case "v":
            func = process_image_d_vertical
        case _:
            func = process_image_d_v1

    paths = get_paths()
    len_paths = len(paths)
    msg = await message.answer(f"Обработка [0/{len_paths}]")
    for i, p in enumerate(paths, start=1):
        func(p)
        await msg.edit_text(f"Обработка [{i}/{len_paths}]")

    path = "./result_images_d"

    media_group = MediaGroupBuilder()
    counter = 0

    for file in os.listdir(path):
        if counter < 10:
            media_group.add_document(media=FSInputFile(f"{path}/{file}"))
            counter += 1
        else:
            await message.bot.send_media_group(
                chat_id=message.chat.id, media=media_group.build()
            )
            media_group = MediaGroupBuilder()
            media_group.add_document(media=FSInputFile(f"{path}/{file}"))
            counter = 1
    if media_group._media:
        await message.bot.send_media_group(
            chat_id=message.chat.id, media=media_group.build()
        )

    clear_dirs_d()
    await message.answer("Все файлы отправлены", reply_markup=ReplyKeyboardRemove())
