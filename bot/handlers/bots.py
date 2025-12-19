from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db.models import Bot, BotFolder, Job, JobName, UserManager
from bot.keyboards.factories import (
    BackFactory,
    BotFolderDeleteFactory,
    BotFolderFactory,
)
from bot.keyboards.inline import ik_available_bots, ik_back, ik_bot_folder_list
from bot.states.main import BotFolderState
from bot.utils import fn

if TYPE_CHECKING:
    pass

router = Router()
logger = logging.getLogger(__name__)

FOLDER_BACK_PREFIX = "bots_folder_"
LIST_BACK_TO = "bots"


async def _show_bots(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
    *,
    folder_id: int | None,
    title: str,
    empty_text: str,
    actions_back_to: str,
    back_to: str = LIST_BACK_TO,
) -> None:
    stmt = (
        select(Bot)
        .options(selectinload(Bot.jobs))
        .where(Bot.user_manager_id == user.id)
        .order_by(
            Bot.is_connected.desc(),
            Bot.is_started.desc(),
            Bot.id.asc(),
        )
    )

    if folder_id == 0:
        stmt = stmt.where(Bot.folder_id.is_(None))
    elif folder_id is not None:
        stmt = stmt.where(Bot.folder_id == folder_id)

    add_to_folder_id = folder_id if folder_id is not None else None
    bots = list((await session.scalars(stmt)).all())
    await state.update_data(bots_back_to=actions_back_to)

    if not bots:
        delete_folder_id = (
            folder_id if folder_id is not None and folder_id != 0 else None
        )
        await query.message.edit_text(
            text=empty_text,
            reply_markup=await ik_available_bots(
                [],
                back_to=back_to,
                delete_folder_id=delete_folder_id,
                add_to_folder_id=add_to_folder_id,
            ),
        )
        return

    for bot in bots:
        is_connected = await fn.Manager.bot_run(bot.phone)
        bot.is_connected = is_connected

        if is_connected and not bot.name:
            has_pending_job = any(
                job.task == JobName.get_me_name.value and job.answer is None
                for job in bot.jobs
            )
            if not has_pending_job:
                bot.jobs.append(Job(task=JobName.get_me_name.value))

    await session.commit()
    await query.message.edit_text(
        title,
        reply_markup=await ik_available_bots(
            bots,
            back_to=back_to,
            add_to_folder_id=add_to_folder_id,
        ),
    )


@router.callback_query(F.data == "bots")
async def show_folders(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    await fn.state_clear(state)

    folders = (
        await session.scalars(
            select(BotFolder)
            .where(BotFolder.user_manager_id == user.id)
            .order_by(BotFolder.id.asc())
        )
    ).all()

    await query.message.edit_text(
        text="Папки",
        reply_markup=await ik_bot_folder_list(list(folders)),
    )


@router.callback_query(F.data == "bots_all")
async def show_all_bots(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    await _show_bots(
        query,
        session,
        state,
        user,
        folder_id=None,
        title="Все боты",
        empty_text="Ботов еще нет",
        actions_back_to="bots_all",
        back_to="default",
    )


@router.callback_query(F.data == "bots_no_folder")
async def show_no_folder_bots(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    await _show_bots(
        query,
        session,
        state,
        user,
        folder_id=0,
        title="Боты без папки",
        empty_text="Ботов без папки еще нет",
        actions_back_to="bots_no_folder",
    )


@router.callback_query(BotFolderFactory.filter())
async def show_folder_bots(
    query: CallbackQuery,
    callback_data: BotFolderFactory,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    await show_folder_bots_by_id(
        query,
        session,
        state,
        user,
        folder_id=callback_data.id,
    )


async def show_folder_bots_by_id(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
    *,
    folder_id: int,
) -> None:
    folder = await session.scalar(
        select(BotFolder).where(
            BotFolder.id == folder_id,
            BotFolder.user_manager_id == user.id,
        )
    )
    if not folder:
        await query.answer(text="Папка не найдена", show_alert=True)
        return

    await _show_bots(
        query,
        session,
        state,
        user,
        folder_id=folder.id,
        title=f"Папка: {folder.name}",
        empty_text="В папке пока нет ботов",
        actions_back_to=f"{FOLDER_BACK_PREFIX}{folder.id}",
    )


@router.callback_query(BotFolderDeleteFactory.filter())
async def delete_folder(
    query: CallbackQuery,
    callback_data: BotFolderDeleteFactory,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    folder = await session.scalar(
        select(BotFolder).where(
            BotFolder.id == callback_data.id,
            BotFolder.user_manager_id == user.id,
        )
    )
    if not folder:
        await query.answer(text="Папка не найдена", show_alert=True)
        return

    has_bots = await session.scalar(
        select(Bot.id).where(Bot.folder_id == folder.id).limit(1)
    )
    if has_bots:
        await query.answer(text="В папке есть боты", show_alert=True)
        return

    await session.delete(folder)
    await session.commit()
    await fn.state_clear(state)

    folders = (
        await session.scalars(
            select(BotFolder)
            .where(BotFolder.user_manager_id == user.id)
            .order_by(BotFolder.id.asc())
        )
    ).all()
    await query.message.edit_text(
        text="Папка удалена",
        reply_markup=await ik_bot_folder_list(list(folders)),
    )


@router.callback_query(F.data == "bots_create_folder")
async def start_create_folder(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(BotFolderState.enter_name)
    await query.message.edit_text(
        text="Введите название папки",
        reply_markup=await ik_back(back_to=LIST_BACK_TO),
    )


@router.message(BotFolderState.enter_name)
async def create_folder(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: UserManager,
) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название папки не может быть пустым")
        return
    if len(name) > 100:
        await message.answer("Название папки слишком длинное (максимум 100)")
        return

    existing = await session.scalar(
        select(BotFolder).where(
            BotFolder.user_manager_id == user.id,
            BotFolder.name == name,
        )
    )
    if existing:
        await message.answer("Папка с таким названием уже существует")
        return

    session.add(BotFolder(name=name, user_manager_id=user.id))
    await session.commit()
    await fn.state_clear(state)

    folders = (
        await session.scalars(
            select(BotFolder)
            .where(BotFolder.user_manager_id == user.id)
            .order_by(BotFolder.id.asc())
        )
    ).all()
    await message.answer(
        text="Папка создана",
        reply_markup=await ik_bot_folder_list(list(folders)),
    )


@router.callback_query(BackFactory.filter(F.to == "bots"))
async def back_bots(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    await show_folders(query, session, state, user)


@router.callback_query(BackFactory.filter(F.to == "bots_all"))
async def back_bots_all(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    await show_all_bots(query, session, state, user)


@router.callback_query(BackFactory.filter(F.to == "bots_no_folder"))
async def back_bots_no_folder(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    await show_no_folder_bots(query, session, state, user)


@router.callback_query(BackFactory.filter(F.to.startswith(FOLDER_BACK_PREFIX)))
async def back_bots_folder(
    query: CallbackQuery,
    callback_data: BackFactory,
    session: AsyncSession,
    state: FSMContext,
    user: UserManager,
) -> None:
    folder_id_str = callback_data.to.replace(FOLDER_BACK_PREFIX, "", 1)
    if not folder_id_str.isdigit():
        await query.answer(text="Некорректный идентификатор папки", show_alert=True)
        return

    await show_folder_bots_by_id(
        query,
        session,
        state,
        user,
        folder_id=int(folder_id_str),
    )
