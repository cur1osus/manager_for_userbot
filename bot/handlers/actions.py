from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.sqlite.models import (
    BannedUser,
    Bot,
    IgnoredWord,
    KeyWord,
    MessageToAnswer,
    MonitoringChat,
)
from bot.keyboards.inline import (
    ik_action_with_bot,
    ik_add_or_delete,
    ik_available_bots,
    ik_cancel_action,
    ik_main_menu,
    ik_num_matrix,
)
from bot.states import UserState
from bot.utils.func import Function as fn
from bot.utils.manager import start_bot, stop_bot

if TYPE_CHECKING:
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)
path_to_folder = "sessions"
sep = "\n"


@router.callback_query(F.data.split(":")[0] == "bot_id")
async def manage_bot(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    bot_id = query.data.split(":")[1]
    await state.update_data(bot_id=bot_id)
    await query.message.edit_text(
        "Выберите действие",
        reply_markup=await ik_action_with_bot(),
    )


@router.callback_query(F.data == "restart_bot")
async def restart_bot(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    bot_id = (await state.get_data())["bot_id"]
    async with sessionmaker() as session:
        bot: Bot = await session.get(Bot, bot_id)
        if not bot:
            return
        phone = bot.phone
    await stop_bot(phone, path_to_folder)

    await start_bot(phone, path_to_folder)
    await query.message.edit_text(
        "Бот подключен и запущен", reply_markup=await ik_main_menu()
    )


@router.callback_query(F.data == "start")
async def start_bot_process(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    bot_id = (await state.get_data())["bot_id"]
    async with sessionmaker() as session:
        bot: Bot = await session.get(Bot, bot_id)
        bot.is_started = True
        await session.commit()
    await query.message.edit_text(
        "Бот Начал писать и анализировать сообщения 🟢"
    )


@router.callback_query(F.data == "stop")
async def stop_bot_process(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    bot_id = (await state.get_data())["bot_id"]
    async with sessionmaker() as session:
        bot: Bot = await session.get(Bot, bot_id)
        bot.is_started = False
        await session.commit()
    await query.message.edit_text(
        "Бот остановлен и не будет писать и анализировать сообщения 🔴",
    )


@router.callback_query(F.data == "delete")
async def delete_bot(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    data = await state.get_data()
    bot_id = data["bot_id"]

    async with sessionmaker() as session:
        bot: Bot = await session.get(Bot, bot_id)
        if bot is None:
            return
        await stop_bot(bot.phone, path_to_folder)
        await session.delete(bot)
        await session.commit()
    await query.message.edit_text("Бот удален", reply_markup=await ik_main_menu())


@router.callback_query(F.data.split(":")[0] == "info")
async def info(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    type_data: str | None = None,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    type_data = type_data or query.data.split(":")[1]
    match type_data:
        case "answer":
            answers = await fn.get_data_from_db(
                sessionmaker, MessageToAnswer, "sentence"
            )
            if not answers:
                await query.message.answer("Ответы отсутствуют")
                return
            answers = await fn.watch_data(answers, sep)
            await query.message.edit_text(
                f"Ответы:\n{answers}",
                reply_markup=await ik_add_or_delete(),
            )
        case "ban":
            banned_users = await fn.get_data_from_db(
                sessionmaker, BannedUser, "username"
            )
            if not banned_users:
                await query.message.answer("Забаненные пользователи отсутствуют")
                return
            banned_users = await fn.watch_data(banned_users, sep)
            await query.message.edit_text(
                f"Забаненные пользователи:\n{banned_users}",
                reply_markup=await ik_add_or_delete(),
            )
        case "chat":
            chats = await fn.get_data_from_db(sessionmaker, MonitoringChat, "id_chat")
            if not chats:
                await query.message.answer("Чаты отсутствуют")
                return
            chats = await fn.watch_data(chats, sep)
            await query.message.edit_text(
                f"Мониторинг чатов:\n{chats}",
                reply_markup=await ik_add_or_delete(),
            )
        case "keyword":
            keywords = await fn.get_data_from_db(sessionmaker, KeyWord, "word")
            if not keywords:
                await query.message.answer("Триггерные слова отсутствуют")
                return
            keywords = await fn.watch_data(keywords, sep)
            await query.message.edit_text(
                f"Триггерные слова:\n{keywords}",
                reply_markup=await ik_add_or_delete(),
            )

        case "ignore":
            ignored_words = await fn.get_data_from_db(sessionmaker, IgnoredWord, "word")
            if not ignored_words:
                await query.message.answer("Игнорируемые слова отсутствуют")
                return
            ignored_words = await fn.watch_data(ignored_words, sep)
            await query.message.edit_text(
                f"Игнорируемые слова:\n{ignored_words}",
                reply_markup=await ik_add_or_delete(),
            )
    await state.set_state(UserState.action)
    await state.update_data(type_data=type_data)


@router.callback_query(UserState.action, F.data == "add")
async def add(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
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
        case "chat":
            await query.message.edit_text(
                "Введите chat_id(-s)", reply_markup=await ik_cancel_action()
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
    await state.set_state(UserState.action)


@router.message(UserState.action)
async def processing_message_to_add(
    message: Message,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if not message.text or isinstance(message, InaccessibleMessage):
        return
    data_to_add = [i.strip() for i in message.text.split(sep)]
    type_data = (await state.get_data())["type_data"]
    match type_data:
        case "answer":
            await fn.add_data_to_db(
                sessionmaker, data_to_add, MessageToAnswer, "sentence"
            )
            data = await fn.get_data_from_db(sessionmaker, MessageToAnswer, "sentence")
        case "ban":
            await fn.add_data_to_db(sessionmaker, data_to_add, BannedUser, "username")
            data = await fn.get_data_from_db(sessionmaker, BannedUser, "username")
            data_txt = await fn.watch_data(data, sep)
        case "chat":
            await fn.add_data_to_db(
                sessionmaker, data_to_add, MonitoringChat, "id_chat"
            )
            data = await fn.get_data_from_db(sessionmaker, MonitoringChat, "id_chat")
        case "ignore":
            await fn.add_data_to_db(sessionmaker, data_to_add, IgnoredWord, "word")
            data = await fn.get_data_from_db(sessionmaker, IgnoredWord, "word")
        case "keyword":
            await fn.add_data_to_db(sessionmaker, data_to_add, KeyWord, "word")
            data = await fn.get_data_from_db(sessionmaker, KeyWord, "word")
    data_txt = await fn.watch_data(data, sep)
    await message.answer(data_txt, reply_markup=await ik_add_or_delete())


@router.callback_query(UserState.action, F.data == "del")
async def delete(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    type_data = (await state.get_data())["type_data"]
    ids = []
    match type_data:
        case "answer":
            ids = await fn.get_data_from_db(sessionmaker, MessageToAnswer, "id")
        case "ban":
            ids = await fn.get_data_from_db(sessionmaker, BannedUser, "id")
        case "chat":
            ids = await fn.get_data_from_db(sessionmaker, MonitoringChat, "id")
        case "ignore":
            ids = await fn.get_data_from_db(sessionmaker, IgnoredWord, "id")
        case "keyword":
            ids = await fn.get_data_from_db(sessionmaker, KeyWord, "id")
        case _:
            return
    await query.message.edit_reply_markup(reply_markup=await ik_num_matrix(ids))
    await state.update_data(ids=ids)
    await state.set_state(UserState.action)


@router.callback_query(UserState.action, F.data.split(":")[0] == "del")
async def del_by_id(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    type_data = (await state.get_data())["type_data"]
    id_ = query.data.split(":")[1]
    async with sessionmaker() as session:
        match type_data:
            case "answer":
                await session.delete(await session.get(MessageToAnswer, int(id_)))
            case "ban":
                await session.delete(await session.get(BannedUser, int(id_)))
            case "chat":
                await session.delete(await session.get(MonitoringChat, int(id_)))
            case "ignore":
                await session.delete(await session.get(IgnoredWord, int(id_)))
            case "keyword":
                await session.delete(await session.get(KeyWord, int(id_)))
        await session.commit()
    await info(query, redis, state, sessionmaker, type_data=type_data)
    await delete(query, redis, state, sessionmaker)


@router.callback_query(UserState.action, F.data == "cancel")
async def cancel_action(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    data = await state.get_data()
    await query.message.edit_text(
        "Выберите действие", reply_markup=await ik_action_with_bot()
    )
    await state.clear()
    await state.update_data(data)


@router.callback_query(UserState.action, F.data.split(":")[0] == "back")
async def back_action(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    to = query.data.split(":")[1]
    match to:
        case "to_add_or_delete":
            await query.message.edit_reply_markup(reply_markup=await ik_add_or_delete())


@router.callback_query(F.data.split(":")[0] == "back")
async def back(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    to = query.data.split(":")[1]
    match to:
        case "to_main_menu":
            await query.message.edit_text(
                "Главное меню", reply_markup=await ik_main_menu()
            )
        case "to_available_bots":
            bots_data = await fn.get_available_bots(sessionmaker)
            await query.message.edit_text(
                "Боты", reply_markup=await ik_available_bots(bots_data)
            )
        case _:
            await query.message.edit_text(
                "Главное меню", reply_markup=await ik_main_menu()
            )
