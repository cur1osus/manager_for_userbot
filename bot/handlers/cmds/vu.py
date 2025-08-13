from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, ReplyKeyboardRemove
from aiogram.utils.media_group import MediaGroupBuilder
from bot.keyboards.inline import ik_main_menu
from bot.keyboards.reply import rk_cancel
from bot.states.main import UserState
from bot.db.mysql.models import UserManager
from bot.utils import fn
from bot.utils.process_v import process_image_v, clear_dirs_v, init_source_v, get_paths
import os

if TYPE_CHECKING:
    from aiogram.types import Message
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command(commands="vu"))
async def vu_cmd(
    message: Message,
    redis: Redis,
    user: UserManager | None,
    state: FSMContext,
) -> None:
    m = await message.answer("Жду файлы", reply_markup=await rk_cancel())
    await fn.set_general_message(state, m)
    await fn.state_clear(state)
    await state.set_state(UserState.send_files)


@router.message(UserState.send_files, F.text == "Отмена")
async def cancel(
    message: Message,
    redis: Redis,
    user: UserManager | None,
    state: FSMContext,
) -> None:
    await fn.state_clear(state)
    await message.answer("Отменено", reply_markup=ReplyKeyboardRemove())
    msg = await message.answer("Hello, world!", reply_markup=await ik_main_menu())
    await fn.set_general_message(state, msg)


@router.message(UserState.send_files, F.document)
async def send_files(
    message: Message,
    redis: Redis,
    user: UserManager | None,
    state: FSMContext,
) -> None:
    await message.bot.download(
        message.document.file_id,
        os.path.join("images_v", f"{message.document.file_name}"),
    )
    await message.answer(f"Файл {message.document.file_name} сохранен")


@router.message(UserState.send_files)
async def vu_end_cmd(
    message: Message,
    redis: Redis,
    user: UserManager | None,
    state: FSMContext,
) -> None:
    await fn.state_clear(state)

    resized_vykupili, new_h, new_w = init_source_v()

    paths = get_paths()
    len_paths = len(paths)
    msg = await message.answer(f"Обработка [0/{len_paths}]")
    for i, p in enumerate(paths, start=1):
        process_image_v(resized_vykupili, new_h, new_w, p)
        await msg.edit_text(f"Обработка [{i}/{len_paths}]")

    path = "./result_images_v"

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

    clear_dirs_v()
    await message.answer("Все файлы отправлены", reply_markup=ReplyKeyboardRemove())
