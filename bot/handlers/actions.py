from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import msgpack  # type: ignore
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.db.mysql.models import (
    BannedUser,
    Bot,
    IgnoredWord,
    Job,
    JobName,
    KeyWord,
    MessageToAnswer,
    MonitoringChat,
    UserManager,
)
from bot.keyboards.inline import (
    ik_action_with_bot,
    ik_add_or_delete,
    ik_available_bots,
    ik_back,
    ik_cancel_action,
    ik_get_processed_users,
    ik_main_menu,
    ik_num_matrix_del,
    ik_num_matrix_users,
    ik_reload_processed_users,
)
from bot.states import UserState
from bot.utils.func import Function as fn
from bot.utils.manager import delete_bot, start_bot

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
        reply_markup=await ik_action_with_bot(back_to="bots"),
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
    await delete_bot(phone, path_to_folder)
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
        "Бот Начал писать и анализировать сообщения 🟢",
        reply_markup=await ik_action_with_bot(),
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
        reply_markup=await ik_action_with_bot(),
    )


@router.callback_query(F.data == "delete")
async def delete_bot_(
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
        await delete_bot(bot.phone, path_to_folder)
        await session.execute(
            delete(MonitoringChat).where(MonitoringChat.bot_id == bot.id)
        )
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
            data = await fn.get_data_from_db(sessionmaker, MessageToAnswer, "sentence")
            data = await fn.watch_data(data, sep) if data else "Ответы отсутствуют"  # type: ignore
            await query.message.edit_text(
                f"Ответы:\n{data}",
                reply_markup=await ik_add_or_delete(),
            )
        case "ban":
            data = await fn.get_data_from_db(sessionmaker, BannedUser, "username")
            data = (
                await fn.watch_data(data, sep) if data else "Пользователи отсутствуют"  # type: ignore
            )
            await query.message.edit_text(
                f"Забаненные пользователи:\n{data}",
                reply_markup=await ik_add_or_delete(),
            )
        case "chat":
            bot_id = (await state.get_data())["bot_id"]
            data = await fn.get_data_from_db(
                sessionmaker,
                MonitoringChat,
                where=["bot_id", bot_id],
            )
            data = await fn.watch_data_chats(data, sep) if data else "Чаты отсутствуют"  # type: ignore
            await query.message.edit_text(
                f"Мониторинг чатов:\n{data}",
                reply_markup=await ik_add_or_delete(back_to="action_with_bot"),  # type: ignore
            )
        case "keyword":
            data = await fn.get_data_from_db(sessionmaker, KeyWord, "word")
            if data:
                data = await fn.watch_data(data, sep)
            else:
                data = "Триггерные слова отсутствуют"  # type: ignore
            await query.message.edit_text(
                f"Триггерные слова:\n{data}",
                reply_markup=await ik_add_or_delete(),
            )

        case "ignore":
            data = await fn.get_data_from_db(sessionmaker, IgnoredWord, "word")
            if data:
                data = await fn.watch_data(data, sep)
            else:
                data = "Игнорируемые слова отсутствуют"  # type: ignore
            await query.message.edit_text(
                f"Игнорируемые слова:\n{data}",
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
                "Введите chat_id(-s)",
                reply_markup=await ik_cancel_action(back_to="add_or_delete"),
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
    kwargs_for_keyboard: dict = {}
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
            bot_id = (await state.get_data())["bot_id"]
            await fn.add_data_to_db(
                sessionmaker,
                data_to_add,
                MonitoringChat,
                "id_chat",
                bot_id=bot_id,
            )
            kwargs_for_keyboard["back_to"] = "action_with_bot"
            data = await fn.get_data_from_db(sessionmaker, MonitoringChat)
            async with sessionmaker() as session:
                job = Job(task=JobName.get_chat_title.value, bot_id=bot_id)
                session.add(job)
                await session.commit()
        case "ignore":
            await fn.add_data_to_db(sessionmaker, data_to_add, IgnoredWord, "word")
            data = await fn.get_data_from_db(sessionmaker, IgnoredWord, "word")
        case "keyword":
            await fn.add_data_to_db(sessionmaker, data_to_add, KeyWord, "word")
            data = await fn.get_data_from_db(sessionmaker, KeyWord, "word")
    data_txt = (
        await fn.watch_data(data, sep)  # type: ignore
        if type_data != "chat"
        else await fn.watch_data_chats(data, sep)  # type: ignore
    )
    await message.answer(
        data_txt, reply_markup=await ik_add_or_delete(**kwargs_for_keyboard)
    )


@router.callback_query(UserState.action, F.data == "del")
async def delete_(
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
    kwargs_for_keyboard: dict = {"back_to": "base_add_or_delete"}
    ids = []
    match type_data:
        case "answer":
            ids = await fn.get_data_from_db(sessionmaker, MessageToAnswer, "id")
        case "ban":
            ids = await fn.get_data_from_db(sessionmaker, BannedUser, "id")
        case "chat":
            bot_id = (await state.get_data())["bot_id"]
            ids = await fn.get_data_from_db(
                sessionmaker, MonitoringChat, "id", ["bot_id", bot_id]
            )
            kwargs_for_keyboard["back_to"] = "chat_add_or_delete"
        case "ignore":
            ids = await fn.get_data_from_db(sessionmaker, IgnoredWord, "id")
        case "keyword":
            ids = await fn.get_data_from_db(sessionmaker, KeyWord, "id")
        case _:
            return
    await query.message.edit_reply_markup(
        reply_markup=await ik_num_matrix_del(ids, **kwargs_for_keyboard)
    )
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
                bot_id = (await state.get_data())["bot_id"]
                await session.delete(
                    await session.scalar(
                        select(MonitoringChat).where(
                            and_(
                                MonitoringChat.id == id_,
                                MonitoringChat.bot_id == bot_id,
                            )
                        )
                    )
                )
            case "ignore":
                await session.delete(await session.get(IgnoredWord, int(id_)))
            case "keyword":
                await session.delete(await session.get(KeyWord, int(id_)))
        await session.commit()
    await info(query, redis, state, sessionmaker, type_data=type_data)
    await delete_(query, redis, state, sessionmaker)


@router.callback_query(F.data == "users_per_minute")
async def users_per_minute(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    user: UserManager,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    await query.message.edit_text(
        text="Выбери пропускную способность:",
        reply_markup=await ik_num_matrix_users(user.users_per_minute),
    )


@router.callback_query(F.data.split(":")[0] == "upm")
async def change_users_per_minute(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    user: UserManager,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    upm = int(query.data.split(":")[1])
    user.users_per_minute = upm
    async with sessionmaker() as session:
        user = await session.merge(user)
        await session.commit()
    await users_per_minute(query, redis, state, sessionmaker, user)


@router.callback_query(F.data == "processed_users")
async def get_processed_users(
    query: CallbackQuery,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    user: UserManager,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    bot_id = (await state.get_data())["bot_id"]
    await state.set_state(UserState.action)
    async with sessionmaker() as session:
        job: Job | None = await session.scalar(
            select(Job).where(
                and_(Job.bot_id == bot_id, Job.task == JobName.processed_users.value)
            )
        )
    if not job:
        await query.message.edit_text(
            text="Чтобы получить нажмите кнопку снизу",
            reply_markup=await ik_get_processed_users(back_to="action_with_bot"),
        )
        return
    if not job.answer:
        await query.message.edit_text(
            text="Задача еще не выполнена",
            reply_markup=await ik_back(back_to="action_with_bot"),
        )
        return
    data = msgpack.unpackb(job.answer)
    txt = data
    if isinstance(data, list):
        txt = await fn.watch_processed_users(data, sep)
    await query.message.edit_text(
        text=txt,
        reply_markup=await ik_reload_processed_users(back_to="action_with_bot"),
    )


@router.callback_query(UserState.action, F.data == "update_processed_users")
async def update_job_to_get_processed_users(
    query: CallbackQuery,
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
    new_job = Job(bot_id=bot_id, task=JobName.processed_users.value)
    async with sessionmaker() as session:
        await session.execute(
            delete(Job).where(
                and_(Job.bot_id == bot_id, Job.task == JobName.processed_users.value)
            )
        )
        session.add(new_job)
        await session.commit()
    await query.message.edit_text(
        text="Задача добавлена и будет выполнена через 5 секунд",
        reply_markup=await ik_back(back_to="action_with_bot"),
    )


@router.callback_query(UserState.action, F.data == "get_processed_users")
async def add_job_to_get_processed_users(
    query: CallbackQuery,
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
    job = Job(bot_id=bot_id, task=JobName.processed_users.value)
    async with sessionmaker() as session:
        session.add(job)
        await session.commit()
    await query.message.edit_text(
        text="Задача добавлена и будет выполнена через 5 секунд",
        reply_markup=await ik_back(back_to="action_with_bot"),
    )


@router.callback_query(UserState.action, F.data.split(":")[0] == "cancel")
async def cancel_action_chat_add_or_delete(
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
    type_data = (await state.get_data())["type_data"]
    match to:
        case "default":
            await info(query, redis, state, sessionmaker, type_data)
        case "add_or_delete":
            await info(query, redis, state, sessionmaker, type_data)


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
        case "default":
            await query.message.edit_text(
                text="Главное меню", reply_markup=await ik_main_menu()
            )
            await state.clear()
        case "action_with_bot":
            data = await state.get_data()
            await query.message.edit_text(
                "Боты", reply_markup=await ik_action_with_bot()
            )
            await state.clear()
            await state.update_data(data)
        case "chat_add_or_delete":
            await query.message.edit_reply_markup(
                reply_markup=await ik_add_or_delete(back_to="action_with_bot"),
            )
        case "base_add_or_delete":
            await query.message.edit_reply_markup(reply_markup=await ik_add_or_delete())


@router.callback_query(F.data == "bots")
async def show_bots(
    query: CallbackQuery,
    redis: Redis,
    sessionmaker: async_sessionmaker,
):
    if not query.message or isinstance(query.message, InaccessibleMessage):
        return
    bots_data = await fn.get_available_bots(sessionmaker)
    async with sessionmaker() as session:
        for bot in bots_data:
            job = Job(task=JobName.get_me_name.value, bot_id=bot.id)
            session.add(job)
        await session.commit()
    await query.message.edit_text(
        "Боты",
        reply_markup=await ik_available_bots(bots_data),
    )


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
        case "default":
            await query.message.edit_text(
                text="Главное меню", reply_markup=await ik_main_menu()
            )
        case "bots":
            bots_data = await fn.get_available_bots(sessionmaker)
            await query.message.edit_text(
                "Боты",
                reply_markup=await ik_available_bots(bots_data),
            )
