from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Optional

import msgpack
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from bot.keyboards.factories import (
    ArrowFoldersFactory,
    BackFactory,
    FolderFactory,
    FolderGetFactory,
    FormattingFactory,
)

from bot.db.mysql.models import (
    Job,
    JobName,
    UserManager,
)
from bot.keyboards.inline import (
    ik_action_with_bot,
    ik_back,
    ik_folders,
    ik_folders_with_users,
    ik_processed_users,
)
from bot.states.main import BotState
from bot.utils import fn
from config import sep


router = Router()
logger = logging.getLogger(__name__)

# Константы
MAX_RETRIES = 3
SLEEP_INTERVAL = 0.5
USERS_PER_PAGE = 2


async def _wait_for_job_completion(
    sessionmaker: async_sessionmaker,
    bot_id: int,
    task_name: str,
    message: Message,
    error_text: str = "Не смог получить данные",
) -> Optional[Job]:
    """Ожидает завершения задачи и возвращает результат."""
    for attempt in range(MAX_RETRIES + 1):
        # Анимация ожидания
        animation_frames = ["", ".", "..", "...", "...."]
        for frame in animation_frames:
            await message.edit_text(text=f"Получаю данные{frame}", reply_markup=None)
            await asyncio.sleep(SLEEP_INTERVAL)

        # Проверка результата
        async with sessionmaker() as session:
            job: Job | None = await session.scalar(
                select(Job)
                .where(
                    and_(
                        Job.bot_id == bot_id,
                        Job.task == task_name,
                    )
                )
                .order_by(Job.id.desc())
                .limit(1)
            )

        if job and job.answer:
            return job

    # Превышено максимальное количество попыток
    await message.edit_text(
        text=error_text,
        reply_markup=await ik_back(back_to="action_with_bot"),
    )
    return None


@router.callback_query(BotState.main, F.data == "processed_users")
async def add_job_to_get_processed_users(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker,
) -> None:
    """Получает список папок для обработанных пользователей."""

    # Создание задачи на получение папок
    data = await state.get_data()
    bot_id = data["bot_id"]
    bot = await user.get_obj_bot(bot_id)
    job = Job(task=JobName.get_folders.value)
    bot.jobs.append(job)
    await session.commit()

    # Ожидание результата
    job_result = await _wait_for_job_completion(
        sessionmaker,
        bot_id,
        JobName.get_folders.value,
        query.message,  # pyright: ignore
    )

    if not job_result:
        await query.message.edit_text(
            "Ошибка при получении папок", reply_markup=await ik_action_with_bot()
        )
        return

    # Обработка результата
    raw_folders: list[dict[str, str]] = msgpack.unpackb(job_result.answer)
    name_folders = [folder["name"] for folder in raw_folders]
    choice_folders = {name: True for name in name_folders}

    await state.set_state(BotState.folders)
    await state.update_data(choice_folders=choice_folders, raw_folders=raw_folders)
    await query.message.edit_text(
        text="Папки",
        reply_markup=await ik_folders(choice_folders, back_to="action_with_bot"),
    )


@router.callback_query(BotState.folders, FolderFactory.filter())
async def choice_folder(
    query: CallbackQuery, state: FSMContext, callback_data: FolderFactory
) -> None:
    """Обрабатывает выбор/отмену выбора папки."""
    data = await state.get_data()
    target_folder = callback_data.name
    choice_folders = data["choice_folders"]

    # Переключаем состояние выбора
    choice_folders[target_folder] = not choice_folders[target_folder]
    await state.update_data(choice_folders=choice_folders)

    await query.message.edit_text(
        text="Папки",
        reply_markup=await ik_folders(choice_folders, back_to="action_with_bot"),
    )


@router.callback_query(BotState.folders, F.data == "accept_folders")
async def get_processed_users_from_folder(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker,
    from_state: bool | None = None,
) -> None:
    """Получает обработанных пользователей из выбранных папок."""
    data = await state.get_data()

    if from_state:
        # Используем данные из состояния
        folders = data.get("folders", [])
        name_folders = [folder["name"] for folder in folders]
    else:
        # Получаем пользователей из выбранных папок
        choice_folders: dict[str, bool] = data["choice_folders"]
        raw_folders: list[dict[str, str]] = data["raw_folders"]
        folders = [  # pyright: ignore
            raw_folder
            for raw_folder in raw_folders
            if choice_folders[raw_folder["name"]]
        ]

        # Создание задачи на получение пользователей
        bot_id = data["bot_id"]
        bot = await user.get_obj_bot(bot_id)
        job = Job(
            task=JobName.processed_users.value, task_metadata=msgpack.packb(folders)
        )
        bot.jobs.append(job)
        await session.commit()

        # Ожидание результата с анимацией
        job_result = await _wait_for_job_completion(
            sessionmaker,
            bot_id,
            JobName.processed_users.value,
            query.message,  # pyright: ignore
            "Не смог получить папки",
        )

        if not job_result:
            return

        folders: list[dict[str, list[dict[str, Any]] | str]] = msgpack.unpackb(
            job_result.answer
        )
        name_folders = [folder["name"] for folder in folders]
        await state.update_data(folders=folders)

    await query.message.edit_text(
        text="Папки",
        reply_markup=await ik_folders_with_users(
            name_folders,  # pyright: ignore
            back_to="action_with_bot",
        ),
    )


@router.callback_query(BotState.folders, FolderGetFactory.filter())
async def view_target_folder(
    query: CallbackQuery,
    state: FSMContext,
    callback_data: FolderGetFactory,
    current_page: int | None = None,
) -> None:
    """Отображает содержимое выбранной папки."""
    data = await state.get_data()

    # Определение текущей папки
    if current_page:
        folder = data["current_folder"]
    else:
        target_folder = callback_data.name
        folders: list[dict[str, dict[str, Any] | str]] = data["folders"]
        folder = next(i for i in folders if i["name"] == target_folder)

    # Настройка пагинации
    page = current_page or 1
    formatting_choices = data.get("formatting_choices", [True, True, False])

    pinned_peers = folder.get("pinned_peers", [])
    all_page = await fn.count_page(len(pinned_peers), USERS_PER_PAGE)

    # Формирование текста для отображения
    formatted_text = await fn.watch_processed_users(
        pinned_peers,  # pyright: ignore
        sep,
        USERS_PER_PAGE,
        page,
        formatting_choices,
    )

    # Обновление состояния
    await state.update_data(
        current_page=page,
        all_page=all_page,
        current_folder=folder,
        formatting_choices=formatting_choices,
    )

    # Отправка сообщения
    display_text = formatted_text if formatted_text else "Папка пустая :("
    await query.message.edit_text(
        display_text,
        reply_markup=await ik_processed_users(
            all_page=all_page,
            current_page=page,
            choices=formatting_choices,
            back_to="accept_folders",
        ),
    )


@router.callback_query(BotState.folders, ArrowFoldersFactory.filter())
async def arrow_processed_users(
    query: CallbackQuery,
    callback_data: ArrowFoldersFactory,
    state: FSMContext,
) -> None:
    """Обрабатывает навигацию по страницам пользователей."""
    arrow = callback_data.to
    data = await state.get_data()

    page = data.get("current_page", 1)
    all_page = data.get("all_page", 1)

    # Обновление номера страницы
    if arrow == "left":
        page = page - 1 if page > 1 else all_page
    elif arrow == "right":
        page = page + 1 if page < all_page else 1

    try:
        await view_target_folder(
            query,
            state,
            FolderGetFactory(name=""),
            current_page=page,
        )
    except Exception as e:
        logger.exception(e)
        await query.answer("Страница всего одна :(")


@router.callback_query(
    BotState.folders,
    FormattingFactory.filter(),
)
async def formatting_(
    query: CallbackQuery, state: FSMContext, callback_data: FormattingFactory
) -> None:
    """Обрабатывает изменение форматирования отображения пользователей."""
    data = await state.get_data()
    formatting_choices: list[bool] = data["formatting_choices"].copy()

    # Обновление настроек форматирования
    format_mapping = {"n": 0, "u": 1, "c": 2}

    if callback_data.format in format_mapping:
        index = format_mapping[callback_data.format]
        formatting_choices[index] = not formatting_choices[index]

    # Гарантируем, что хотя бы один параметр форматирования включен
    if not any(formatting_choices[:2]):  # Проверяем первые два элемента
        formatting_choices[0] = True

    await state.update_data(formatting_choices=formatting_choices)

    # Обновляем отображение
    with contextlib.suppress(Exception):
        await view_target_folder(
            query,
            state,
            FolderGetFactory(name=""),
            current_page=data["current_page"],
        )


@router.callback_query(BotState.folders, BackFactory.filter(F.to == "action_with_bot"))
async def back_action_with_bot(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    data = (await state.get_data()).copy()
    await query.message.edit_text("Боты", reply_markup=await ik_action_with_bot())
    await fn.state_clear(state)
    await state.set_state(BotState.main)
    await state.update_data(data)


@router.callback_query(BotState.folders, BackFactory.filter(F.to == "accept_folders"))
async def back_accept_folders(
    query: CallbackQuery,
    state: FSMContext,
    user: UserManager,
    session: AsyncSession,
    sessionmaker: async_sessionmaker,
) -> None:
    await get_processed_users_from_folder(
        query,
        user,
        state,
        session,
        sessionmaker,
        from_state=True,
    )
