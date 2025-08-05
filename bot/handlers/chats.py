from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.mysql.models import (
    Bot,
    Job,
    JobName,
    MonitoringChat,
)
from bot.states.main import BotState, InfoState
from bot.keyboards.inline import (
    ik_action_with_bot,
    ik_add_or_delete,
    ik_cancel_action,
    ik_num_matrix_del,
)
from bot.keyboards.factories import (
    CancelFactory,
    DeleteInfoFactory,
    InfoFactory,
    ArrowInfoFactory,
    BackFactory,
)
from bot.utils import fn
from config import sep

if TYPE_CHECKING:
    pass

router = Router()
logger = logging.getLogger(__name__)


async def data_info_to_string(
    data: list[MonitoringChat],
    q_string_per_page: int = 10,
    current_page: int | None = None,
) -> tuple[str, int, int]:
    all_page = await fn.count_page(
        len_data=len(data), q_string_per_page=q_string_per_page
    )
    current_page = current_page or all_page
    data_str = await fn.watch_data_chats(
        data,
        sep,
        q_string_per_page,
        current_page,
    )
    if not data_str:
        data_str = "Нет данных"
    return data_str, current_page, all_page


@router.callback_query(BotState.main, InfoFactory.filter(F.key == "chats"))
async def info_chats(
    query: CallbackQuery | Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data_state = await state.get_data()
    bot = await session.get(Bot, data_state["bot_id"])

    data = await bot.awaitable_attrs.chats
    data_str, current_page, all_page = await data_info_to_string(data)

    await query.message.edit_text(
        text=data_str,
        reply_markup=await ik_add_or_delete(current_page, all_page),
    )

    await state.set_state(InfoState.chats_info)
    await state.update_data(
        current_page=current_page,
        all_page=all_page,
    )


@router.callback_query(InfoState.chats_info, ArrowInfoFactory.filter())
async def arrow_chats_info(
    query: CallbackQuery,
    callback_data: ArrowInfoFactory,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    arrow = callback_data.to
    data_state = await state.get_data()
    page = data_state["current_page"]
    all_page = data_state["all_page"]
    match arrow:
        case "left":
            page = page - 1 if page > 1 else all_page
        case "right":
            page = page + 1 if page < all_page else 1
    await state.update_data(current_page=page)
    try:
        bot = await session.get(Bot, data_state["bot_id"])
        data = await bot.awaitable_attrs.chats
        data_str, current_page, all_page = await data_info_to_string(
            data,
            current_page=page,
        )
        await query.message.edit_text(
            text=data_str,
            reply_markup=await ik_add_or_delete(current_page, all_page),
        )
    except Exception:
        await query.answer("Страница всего одна :(")


@router.callback_query(InfoState.chats_info, F.data == "add")
async def add_chats(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    await query.message.edit_text(
        "Введите id чата(-ов)", reply_markup=await ik_cancel_action()
    )
    await state.set_state(InfoState.chats_add)


@router.message(InfoState.chats_add)
async def chats_message_to_add(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data_to_add = [i.strip() for i in message.text.split(sep) if i]
    data_state = await state.get_data()

    bot = await session.get(Bot, data_state["bot_id"])
    chats = await bot.awaitable_attrs.chats
    chats.extend(MonitoringChat(chat_id=int(i)) for i in data_to_add)

    job = Job(task=JobName.get_chat_title.value)
    bot.jobs.append(job)

    await session.commit()
    current_page = (await state.get_data())["current_page"]

    data = chats
    data_str, current_page, all_page = await data_info_to_string(
        data, current_page=current_page
    )
    msg = await message.answer(
        text=data_str,
        reply_markup=await ik_add_or_delete(current_page, all_page),
    )
    await fn.set_general_message(state, msg)
    await state.set_state(InfoState.chats_info)


@router.callback_query(InfoState.chats_info, F.data == "delete")
async def delete_chats(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data_state = await state.get_data()
    bot = await session.get(Bot, data_state["bot_id"])
    ids = [i.id for i in bot.chats]
    await query.message.edit_reply_markup(
        reply_markup=await ik_num_matrix_del(ids, "info")
    )
    await state.set_state(InfoState.chats_delete)
    await state.update_data(ids=ids)


@router.callback_query(InfoState.chats_delete, DeleteInfoFactory.filter())
async def chats_delete_by_id_obj(
    query: CallbackQuery,
    callback_data: DeleteInfoFactory,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker,
) -> None:
    data_state = await state.get_data()

    bot = await session.get(Bot, data_state["bot_id"])
    chats = await bot.awaitable_attrs.chats
    id_ = callback_data.id
    obj = [chat for chat in chats if chat.id == id_]

    if not obj:
        await query.answer("Объект не найден")
        return

    bot.chats.remove(obj[0])
    await session.commit()

    async with sessionmaker() as session:
        bot_updated = await session.get(Bot, bot.id)

    if not bot_updated:
        await query.answer("Бот не найден")
        return

    ids = [chat.id for chat in bot_updated.chats]
    data_str, _, _ = await data_info_to_string(
        bot_updated.chats, current_page=data_state["current_page"]
    )
    await state.update_data(ids=ids)
    await query.message.edit_text(
        text=data_str, reply_markup=await ik_num_matrix_del(ids, "info")
    )


@router.callback_query(InfoState.chats_delete, BackFactory.filter(F.to == "info"))
async def back_info(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await info_chats(query, state, session)


@router.callback_query(InfoState.chats_info, BackFactory.filter(F.to == "default"))
async def back_chats(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    await query.message.edit_text("Действуй!", reply_markup=await ik_action_with_bot())
    await fn.state_clear(state)
    await state.set_state(BotState.main)
    await state.update_data(data)


@router.callback_query(InfoState.add, CancelFactory.filter(F.to == "default"))
async def cancel_chats(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data_state = await state.get_data()
    bot = await session.get(Bot, data_state["bot_id"])
    current_page = data_state["current_page"]

    data = await bot.awaitable_attrs.chats
    data_str, current_page, all_page = await data_info_to_string(data)

    msg = await query.message.answer(
        text=data_str,
        reply_markup=await ik_add_or_delete(current_page, all_page),
    )
    await fn.set_general_message(state, msg)
    await state.set_state(BotState.main)
