from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Final

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.types.reply_keyboard_remove import ReplyKeyboardRemove
from aiogram.utils.media_group import MediaGroupBuilder

from bot.db.models import UserManager
from bot.keyboards.inline import ik_main_menu
from bot.keyboards.reply import (
    BTN_CANCEL,
    BTN_CLEAR,
    BTN_FILES,
    BTN_START,
    rk_processing,
)
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

ALLOWED_EXTENSIONS: Final[set[str]] = {".png", ".jpg", ".jpeg"}
MODE_BUTTON_PREFIX: Final[str] = "⚙️ Режим: "

DEFAULT_DO_MODE: Final[str] = "w"
DO_MODE_ORDER: Final[list[str]] = ["w", "b", "v"]
DO_MODE_LABELS: Final[dict[str, str]] = {
    "w": "W — базовый",
    "b": "B — черный",
    "v": "V — вертикальный",
}
DO_MODE_FUNCS: Final[dict[str, Callable[[str], bool]]] = {
    "w": process_image_d_v1,
    "b": process_image_d_v2,
    "v": process_image_d_vertical,
}

FILES_PREVIEW_LIMIT: Final[int] = 20


def _mode_button_label(mode: str) -> str:
    label = DO_MODE_LABELS.get(mode, DO_MODE_LABELS[DEFAULT_DO_MODE])
    return f"{MODE_BUTTON_PREFIX}{label}"


async def _current_mode(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("do_mode", DEFAULT_DO_MODE)


def _next_mode(mode: str) -> str:
    try:
        idx = DO_MODE_ORDER.index(mode)
    except ValueError:
        return DEFAULT_DO_MODE
    return DO_MODE_ORDER[(idx + 1) % len(DO_MODE_ORDER)]


async def _processing_keyboard(state: FSMContext):
    mode = await _current_mode(state)
    return await rk_processing(_mode_button_label(mode))


def _render_queue(paths: list[str]) -> str:
    if not paths:
        return "Очередь пуста. Пришли PNG как документ."

    preview = [Path(p).name for p in paths[:FILES_PREVIEW_LIMIT]]
    body = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(preview))
    tail = ""
    if len(paths) > len(preview):
        tail = f"\n... и еще {len(paths) - len(preview)} файл(ов)"
    return f"В очереди {len(paths)} файл(ов):\n{body}{tail}"


async def _send_results(message: Message, folder: str) -> None:
    if not os.path.isdir(folder):
        await message.answer("Готовых файлов нет.")
        return

    files = sorted(os.listdir(folder))
    if not files:
        await message.answer("Готовых файлов нет.")
        return

    media_group = MediaGroupBuilder()
    counter = 0

    for file in files:
        if counter < 10:
            media_group.add_document(media=FSInputFile(f"{folder}/{file}"))
            counter += 1
        else:
            await message.bot.send_media_group(
                chat_id=message.chat.id, media=media_group.build()
            )
            media_group = MediaGroupBuilder()
            media_group.add_document(media=FSInputFile(f"{folder}/{file}"))
            counter = 1
    if media_group._media:
        await message.bot.send_media_group(
            chat_id=message.chat.id, media=media_group.build()
        )


@router.message(Command(commands="do"))
async def do_cmd(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    await fn.state_clear(state)
    await state.set_state(UserState.send_files_do)
    await state.update_data(do_mode=DEFAULT_DO_MODE)

    intro = (
        "Загрузите PNG/JPG как документ, затем жмите «🚀 Старт».\n"
        "⚙️ Режимы: W — базовый, B — контраст, V — вертикальный.\n"
        "📂 «Файлы» — покажу очередь, 🧹 «Очистить» — удалю все загруженное."
    )
    m = await message.answer(intro, reply_markup=await _processing_keyboard(state))
    await fn.set_general_message(state, m)


@router.message(UserState.send_files_do, F.text == BTN_CANCEL)
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
    file_name = message.document.file_name or "file"
    ext = Path(file_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        await message.answer("Принимаю PNG/JPG/JPEG. Отправьте файл как документ.")
        return

    target = Path("images_d") / Path(file_name).name
    target.parent.mkdir(parents=True, exist_ok=True)

    await message.bot.download(
        message.document.file_id,
        target,
    )
    paths = get_paths()
    await message.answer(
        f"Файл {target.name} сохранен. В очереди {len(paths)}.",
        reply_markup=await _processing_keyboard(state),
    )


@router.message(UserState.send_files_do, F.text == BTN_FILES)
async def show_queue(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    text = _render_queue(get_paths())
    await message.answer(text, reply_markup=await _processing_keyboard(state))


@router.message(UserState.send_files_do, F.text == BTN_CLEAR)
async def clear_queue(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    clear_dirs_d()
    await message.answer(
        "Очередь и результаты очищены.", reply_markup=await _processing_keyboard(state)
    )


@router.message(UserState.send_files_do, F.text.startswith(MODE_BUTTON_PREFIX))
async def switch_mode(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    mode = _next_mode(await _current_mode(state))
    await state.update_data(do_mode=mode)
    await message.answer(
        f"Режим переключен на {DO_MODE_LABELS[mode]}.",
        reply_markup=await _processing_keyboard(state),
    )


@router.message(UserState.send_files_do, F.text == BTN_START)
async def do_start(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    paths = get_paths()
    len_paths = len(paths)
    if not len_paths:
        await message.answer(
            "Очередь пуста. Пришлите PNG/JPG как документ.",
            reply_markup=await _processing_keyboard(state),
        )
        return

    mode = await _current_mode(state)
    func = DO_MODE_FUNCS.get(mode, process_image_d_v1)

    msg = await message.answer(f"Обработка [0/{len_paths}]")
    success = 0
    for i, p in enumerate(paths, start=1):
        if func(p):
            success += 1
        await msg.edit_text(f"Обработка [{i}/{len_paths}]")

    await _send_results(message, "./result_images_d")
    clear_dirs_d()

    await message.answer(
        f"Готово: {success}/{len_paths} файлов обработаны.",
        reply_markup=await _processing_keyboard(state),
    )


@router.message(UserState.send_files_do)
async def fallback(
    message: Message,
    redis: Redis,
    user: UserManager,
    state: FSMContext,
) -> None:
    await message.answer(
        "Пришлите PNG/JPG как документ или используйте кнопки ниже.",
        reply_markup=await _processing_keyboard(state),
    )
