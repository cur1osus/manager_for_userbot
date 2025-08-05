from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.mysql.models import (
    BannedUser,
    IgnoredWord,
    KeyWord,
    MessageToAnswer,
    UserManager,
)
from bot.states.main import InfoState
from bot.keyboards.inline import (
    ik_add_or_delete,
    ik_cancel_action,
    ik_num_matrix_del,
    ik_main_menu,
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
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


async def get_data_for_info(user: UserManager, type_data: str) -> list[str]:
    match type_data:
        case "answer":
            return [i.sentence for i in user.messages_to_answer]
        case "ban":
            return [i.username for i in user.banned_users]
        case "keyword":
            return [i.word for i in user.keywords]
        case "ignore":
            return [i.word for i in user.ignored_words]
    return []


async def get_ids_for_info(user: UserManager, type_data: str) -> list[int]:
    match type_data:
        case "answer":
            return [i.id for i in user.messages_to_answer]
        case "ban":
            return [i.id for i in user.banned_users]
        case "keyword":
            return [i.id for i in user.keywords]
        case "ignore":
            return [i.id for i in user.ignored_words]
    return []


async def get_obj_for_info(
    type_data: str,
    session: AsyncSession,
    id_: int,
) -> Any:
    match type_data:
        case "answer":
            return await session.get(MessageToAnswer, id_)
        case "ban":
            return await session.get(BannedUser, id_)
        case "ignore":
            return await session.get(IgnoredWord, id_)
        case "keyword":
            return await session.get(KeyWord, id_)
    return None


async def data_info_to_string(
    data: list[str],
    q_string_per_page: int = 10,
    current_page: int | None = None,
) -> tuple[str, int, int]:
    all_page = await fn.count_page(
        len_data=len(data), q_string_per_page=q_string_per_page
    )
    current_page = current_page or all_page
    data_str = await fn.watch_data(
        data,
        sep,
        q_string_per_page,
        current_page,
    )
    if not data_str:
        data_str = "Нет данных"
    return data_str, current_page, all_page


@router.callback_query(InfoFactory.filter())
async def info(
    query: CallbackQuery | Message,
    user: UserManager,
    state: FSMContext,
    callback_data: InfoFactory,
) -> None:
    type_data = callback_data.key

    data = await get_data_for_info(user, type_data)
    data_str, current_page, all_page = await data_info_to_string(data)

    await query.message.edit_text(
        text=data_str,
        reply_markup=await ik_add_or_delete(current_page, all_page),
    )

    await state.set_state(InfoState.info)
    await state.update_data(
        type_data=type_data,
        current_page=current_page,
        all_page=all_page,
    )


@router.callback_query(InfoState.info, ArrowInfoFactory.filter())
async def arrow_info(
    query: CallbackQuery,
    callback_data: ArrowInfoFactory,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    arrow = callback_data.to
    data_state = await state.get_data()
    page = data_state["current_page"]
    all_page = data_state["all_page"]
    type_data = data_state["type_data"]
    match arrow:
        case "left":
            page = page - 1 if page > 1 else all_page
        case "right":
            page = page + 1 if page < all_page else 1
    await state.update_data(current_page=page)
    try:
        data = await get_data_for_info(user, type_data)
        data_str, current_page, all_page = await data_info_to_string(
            data=data, current_page=page
        )
        await query.message.edit_text(
            text=data_str,
            reply_markup=await ik_add_or_delete(current_page, all_page),
        )
    except Exception:
        await query.answer("Страница всего одна :(")


@router.callback_query(InfoState.info, F.data == "add")
async def add(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    type_data = (await state.get_data())["type_data"]
    match type_data:
        case "answer":
            await query.message.edit_text(
                "Введите ответ(-ы)", reply_markup=await ik_cancel_action()
            )
        case "ban":
            await query.message.edit_text(
                "Введите username(-s)", reply_markup=await ik_cancel_action()
            )
        case "ignore":
            await query.message.edit_text(
                "Введите слово(-а) (или предложение(-я)) для игнорирования",
                reply_markup=await ik_cancel_action(),
            )
        case "keyword":
            await query.message.edit_text(
                "Введите триггерное слово(-а)", reply_markup=await ik_cancel_action()
            )
    await state.set_state(InfoState.add)


@router.message(InfoState.add)
async def processing_message_to_add(
    message: Message,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data_to_add = [i.strip() for i in message.text.split(sep) if i]
    type_data = (await state.get_data())["type_data"]
    match type_data:
        case "answer":
            messages_to_answer = await user.awaitable_attrs.messages_to_answer
            data_to_add = await fn.collapse_repeated_data(
                [i.sentence for i in messages_to_answer], data_to_add
            )
            messages_to_answer.extend(
                [MessageToAnswer(sentence=i) for i in data_to_add]
            )
        case "ban":
            banned_users = await user.awaitable_attrs.banned_users
            data_to_add = await fn.collapse_repeated_data(
                [i.username for i in banned_users], data_to_add
            )
            banned_users.extend([BannedUser(username=i) for i in data_to_add])
        case "ignore":
            ignored_words = await user.awaitable_attrs.ignored_words
            data_to_add = await fn.collapse_repeated_data(
                [i.word for i in ignored_words], data_to_add
            )
            ignored_words.extend([IgnoredWord(word=i) for i in data_to_add])
        case "keyword":
            keywords = await user.awaitable_attrs.keywords
            data_to_add = await fn.collapse_repeated_data(
                [i.word for i in keywords], data_to_add
            )
            keywords.extend([KeyWord(word=i) for i in data_to_add])
    await session.commit()
    current_page = (await state.get_data())["current_page"]

    data = await get_data_for_info(user, type_data)
    data_str, current_page, all_page = await data_info_to_string(
        data, current_page=current_page
    )
    msg = await message.answer(
        text=data_str,
        reply_markup=await ik_add_or_delete(current_page, all_page),
    )
    await fn.set_general_message(state, msg)
    await state.set_state(InfoState.info)


@router.callback_query(InfoState.info, F.data == "delete")
async def delete(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
) -> None:
    type_data = (await state.get_data())["type_data"]
    ids = await get_ids_for_info(user, type_data)
    await query.message.edit_reply_markup(
        reply_markup=await ik_num_matrix_del(ids, "info")
    )
    await state.set_state(InfoState.delete)
    await state.update_data(ids=ids)


@router.callback_query(InfoState.delete, DeleteInfoFactory.filter())
async def delete_by_id_obj(
    query: CallbackQuery,
    callback_data: DeleteInfoFactory,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker,
) -> None:
    type_data = (await state.get_data())["type_data"]
    id_ = callback_data.id
    obj = await get_obj_for_info(type_data, session, id_)

    if obj is None:
        await query.answer("Объект не найден")
        return

    await session.delete(obj)
    await session.commit()

    async with sessionmaker() as session:
        user_updated = await session.get(UserManager, user.id)

    if not user_updated:
        await query.answer("Пользователь не найден")
        return

    type_data = (await state.get_data())["type_data"]

    data = await get_data_for_info(user_updated, type_data)
    data_str, current_page, all_page = await data_info_to_string(data)

    ids = await get_ids_for_info(user_updated, type_data)
    await query.message.edit_text(
        text=data_str, reply_markup=await ik_num_matrix_del(ids, "info")
    )
    await state.update_data(ids=ids)


@router.callback_query(InfoState.delete, BackFactory.filter(F.to == "info"))
async def back_info(
    query: CallbackQuery,
    state: FSMContext,
    user: UserManager,
) -> None:
    key = (await state.get_data())["type_data"]
    await info(query, user, state, InfoFactory(key=key))


@router.callback_query(InfoState.info, BackFactory.filter(F.to == "default"))
async def back(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    await fn.state_clear(state)
    await query.message.edit_text("Главное меню", reply_markup=await ik_main_menu())


@router.callback_query(InfoState.add, CancelFactory.filter(F.to == "default"))
async def cancel(
    query: CallbackQuery,
    state: FSMContext,
    user: UserManager,
) -> None:
    current_page = (await state.get_data())["current_page"]
    type_data = (await state.get_data())["type_data"]

    data = await get_data_for_info(user, type_data)
    data_str, current_page, all_page = await data_info_to_string(
        data, current_page=current_page
    )

    msg = await query.message.answer(
        text=data_str,
        reply_markup=await ik_add_or_delete(current_page, all_page),
    )
    await fn.set_general_message(state, msg)
    await state.set_state(InfoState.info)
