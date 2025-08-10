from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from bot.states.main import UserState
from bot.db.mysql.models import UserManager
from bot.utils import fn
from bot.utils.process_v import process_image_v, clear_dirs_v
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
    m = await message.answer("Жду файлы")
    await fn.set_general_message(state, m)
    await fn.state_clear(state)
    await state.set_state(UserState.send_files)


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
    process_image_v()
    path = "./result_images_v"
    for file in os.listdir(path):
        await message.bot.send_document(
            chat_id=message.chat.id,
            document=FSInputFile(f"{path}/{file}"),
        )
    clear_dirs_v()
    await message.answer("Файлы отправлены")
