from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

import msgpack  # type: ignore
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InaccessibleMessage, Message
from sqlalchemy import and_, asc, delete, select
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
    UserAnalyzed,
    UserManager,
)
from bot.keyboards.inline import (
    ik_action_with_bot,
    ik_add_or_delete,
    ik_available_bots,
    ik_back,
    ik_cancel_action,
    ik_folders,
    ik_history_back,
    ik_main_menu,
    ik_num_matrix_del,
    ik_num_matrix_users,
    ik_processed_users,
)
from bot.states import UserState
from bot.utils.func import Function as fn
from bot.utils.manager import delete_bot, start_bot

if TYPE_CHECKING:
    from redis.asyncio import Redis
from sqlalchemy import func

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
    query: CallbackQuery | Message,
    redis: Redis,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    type_data: str | None = None,
    current_page: int | None = None,
):
    if isinstance(query, CallbackQuery):
        if (
            not query.data
            or not query.message
            or isinstance(query.message, InaccessibleMessage)
        ):
            return
        type_data = type_data or query.data.split(":")[1]
    kwargs_for_keyboard: dict = {}
    all_page = None
    data_str = None
    match type_data:
        case "answer":
            data = await fn.get_data_from_db(sessionmaker, MessageToAnswer, "sentence")
            data_str = None if data else "Ответы отсутствуют"
        case "ban":
            data = await fn.get_data_from_db(sessionmaker, BannedUser, "username")
            data_str = None if data else "Пользователи отсутствуют"
        case "chat":
            bot_id = (await state.get_data())["bot_id"]
            data = await fn.get_data_from_db(
                sessionmaker,
                MonitoringChat,
                where=["bot_id", bot_id],
            )
            q_string_per_page = 10
            all_page = await fn.count_page(
                len_data=len(data), q_string_per_page=q_string_per_page
            )
            current_page = current_page or all_page
            data_str = (
                await fn.watch_data_chats(
                    data,  # type: ignore
                    sep,
                    q_string_per_page,
                    current_page or all_page,
                )
                if data
                else "Чаты отсутствуют"
            )
            kwargs_for_keyboard = {
                "back_to": "action_with_bot",
                "current_page": current_page,
                "all_page": all_page,
            }
        case "keyword":
            data = await fn.get_data_from_db(sessionmaker, KeyWord, "word")
            data_str = None if data else "Триггерные слова отсутствуют"

        case "ignore":
            data = await fn.get_data_from_db(sessionmaker, IgnoredWord, "word")
            data_str = None if data else "Игнорируемые слова отсутствуют"

    if not data_str:
        q_string_per_page = 10
        all_page = await fn.count_page(
            len_data=len(data), q_string_per_page=q_string_per_page
        )
        current_page = current_page or all_page
        data_str = await fn.watch_data(
            data,
            sep,
            q_string_per_page,
            current_page,  # type: ignore
        )
    kwargs_for_keyboard["all_page"] = all_page or 1
    kwargs_for_keyboard["current_page"] = current_page or 1
    if isinstance(query, CallbackQuery):
        await query.message.edit_text(  # type: ignore
            text=data_str,
            reply_markup=await ik_add_or_delete(**kwargs_for_keyboard),
        )
    else:
        await query.answer(
            text=data_str,
            reply_markup=await ik_add_or_delete(**kwargs_for_keyboard),
        )
    await state.set_state(UserState.action)
    await state.update_data(
        type_data=type_data,
        current_page=current_page,
        all_page=all_page,
    )


@router.callback_query(F.data.in_(["arrow_left", "arrow_right"]))
async def arrow(
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
    arrow = query.data
    data = await state.get_data()
    page = data.get("current_page", 1)
    all_page = data.get("all_page", 1)
    type_data = data.get("type_data")
    match arrow:
        case "arrow_left":
            page = page - 1 if page > 1 else all_page
        case "arrow_right":
            page = page + 1 if page < all_page else 1
    try:
        await info(
            query, redis, state, sessionmaker, type_data=type_data, current_page=page
        )
    except Exception:
        await query.answer("Страница всего одна :(")


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
    match type_data:
        case "answer":
            await fn.add_data_to_db(
                sessionmaker, data_to_add, MessageToAnswer, "sentence"
            )
        case "ban":
            await fn.add_data_to_db(sessionmaker, data_to_add, BannedUser, "username")
        case "chat":
            bot_id = (await state.get_data())["bot_id"]
            await fn.add_data_to_db(
                sessionmaker,
                data_to_add,
                MonitoringChat,
                "id_chat",
                bot_id=bot_id,
            )
            async with sessionmaker() as session:
                job = Job(task=JobName.get_chat_title.value, bot_id=bot_id)
                session.add(job)
                await session.commit()
        case "ignore":
            await fn.add_data_to_db(sessionmaker, data_to_add, IgnoredWord, "word")
        case "keyword":
            await fn.add_data_to_db(sessionmaker, data_to_add, KeyWord, "word")
    current_page = (await state.get_data())["current_page"]
    await info(
        message,
        redis,
        state,
        sessionmaker,
        type_data=type_data,
        current_page=current_page,
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
async def add_job_to_get_processed_users(
    query: CallbackQuery,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    from_state: bool = False,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    if from_state:
        folders = (await state.get_data())["folders"]
        folders_name = [folder[0] for folder in folders]
    else:
        bot_id = (await state.get_data())["bot_id"]
        await state.set_state(UserState.action)
        job = Job(bot_id=bot_id, task=JobName.processed_users.value)
        async with sessionmaker() as session:
            session.add(job)
            await session.commit()
            switch = True
            tries = 0
            while switch:
                await query.message.edit_text(text="Получаю папки", reply_markup=None)
                folders: Job | None = await session.scalar(  # type: ignore
                    select(Job).where(
                        and_(
                            Job.bot_id == bot_id,
                            Job.task == JobName.processed_users.value,
                        )
                    )
                )
                await asyncio.sleep(1)
                await query.message.edit_text(text="Получаю папки.")
                await asyncio.sleep(1)
                await query.message.edit_text(text="Получаю папки..")
                await asyncio.sleep(1)
                await query.message.edit_text(text="Получаю папки...")
                if folders and folders.answer:
                    switch = False
                if tries > 3:
                    await query.message.edit_text(
                        text="Не смог получить папки",
                        reply_markup=await ik_back(back_to="action_with_bot"),
                    )
                    return
                tries += 1
        folders_unpack = msgpack.unpackb(folders.answer)  # type: ignore
        folders_name = [folder[0] for folder in folders_unpack]
        await state.update_data(folders=folders_unpack)
    await query.message.edit_text(
        text="Папки",
        reply_markup=await ik_folders(folders_name, back_to="action_with_bot"),
    )


@router.callback_query(UserState.action, F.data.split(":")[0] == "folder")
async def get_processed_users_from_folder(
    query: CallbackQuery,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    current_page: int | None = None,
    from_state: bool = False,
    formatting_choices: list[bool] | None = None,
):
    if formatting_choices is None:
        formatting_choices = [True, True, False]
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    if from_state:
        folder = (await state.get_data()).get("folder", None)
        name_folder, processed_users = folder
    else:
        name_target_folder = query.data.split(":")[1]
        folders = (await state.get_data())["folders"]
        name_folder, processed_users = [
            i for i in folders if i[0] == name_target_folder
        ][0]
    q_string_per_page = 20
    all_page = await fn.count_page(
        len_data=len(processed_users), q_string_per_page=q_string_per_page
    )
    current_page = current_page or all_page
    txt = processed_users or "Нет людей"
    if isinstance(txt, list):
        txt = await fn.watch_processed_users(
            processed_users, sep, q_string_per_page, current_page, formatting_choices
        )
        await state.update_data(
            current_page=current_page,
            all_page=all_page,
            folder=[name_folder, processed_users],
        )
    await state.update_data(formatting_choices=formatting_choices)
    await query.message.edit_text(
        text=txt,
        reply_markup=await ik_processed_users(
            back_to="folders",
            current_page=current_page,
            all_page=all_page,
            choices=formatting_choices,
        ),
    )


@router.callback_query(UserState.action, F.data.split(":")[0] == "u")
async def arrow_processed_users(
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
    arrow = query.data.split(":")[1]
    data = await state.get_data()
    page = data.get("current_page", 1)
    all_page = data.get("all_page", 1)
    match arrow:
        case "arrow_left":
            page = page - 1 if page > 1 else all_page
        case "arrow_right":
            page = page + 1 if page < all_page else 1
    try:
        await get_processed_users_from_folder(
            query, state, sessionmaker, current_page=page, from_state=True
        )
    except Exception as e:
        logger.exception(e)
        await query.answer("Страница всего одна :(")


@router.callback_query(
    UserState.action, F.data.in_(["f_username", "f_first_name", "f_copy"])
)
async def formatting_(
    query: CallbackQuery,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    current_page: int | None = None,
):
    formatting_choices: list[bool] = (await state.get_data()).get(
        "formatting_choices", None
    )
    if query.data == "f_first_name":
        formatting_choices[0] = not formatting_choices[0]
    elif query.data == "f_username":
        formatting_choices[1] = not formatting_choices[1]
    elif query.data == "f_copy":
        formatting_choices[2] = not formatting_choices[2]
    if formatting_choices[0] is False and formatting_choices[1] is False:
        formatting_choices[0] = True
    with contextlib.suppress(Exception):
        await get_processed_users_from_folder(
            query,
            state,
            sessionmaker,
            current_page=None,
            from_state=True,
            formatting_choices=formatting_choices,
        )


@router.callback_query(F.data == "history")
async def history(
    query: CallbackQuery,
    state: FSMContext,
    sessionmaker: async_sessionmaker,
    current_page: int | None = None,
):
    if (
        not query.data
        or not query.message
        or isinstance(query.message, InaccessibleMessage)
    ):
        return
    q_string_per_page = 10
    async with sessionmaker() as session:
        len_data = await session.scalar(select(func.count(UserAnalyzed.id)))
        all_page = await fn.count_page(len_data, q_string_per_page)
        current_page = current_page or all_page
        user_analyzed: list[UserAnalyzed] = (
            await session.scalars(
                select(UserAnalyzed)
                .order_by(asc(UserAnalyzed.id))
                .slice(
                    (current_page - 1) * q_string_per_page,
                    current_page * q_string_per_page,
                )
            )
        ).all()
        t = ""
        for user in user_analyzed:
            msg = user.additional_message[:10].replace("\n", "")
            t += f"{user.id}. {'🟢' if user.sended else '🔴'} @{user.username} - {msg}...\n"
    if not t:
        await query.message.edit_text(
            text="История пуста", reply_markup=await ik_back()
        )
        return
    if len(t) > fn.max_length_message:
        t = t[: fn.max_length_message - 4]
        t += "..."
    await state.update_data(current_page=current_page, all_page=all_page)
    await query.message.edit_text(
        text=t,
        reply_markup=await ik_history_back(
            all_page=all_page,
            current_page=current_page,
        ),
    )


@router.callback_query(F.data.split(":")[0] == "h")
async def arrow_history(
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
    arrow = query.data.split(":")[1]
    data = await state.get_data()
    page = data.get("current_page", 1)
    all_page = data.get("all_page", 1)
    match arrow:
        case "arrow_left":
            page = page - 1 if page > 1 else all_page
        case "arrow_right":
            page = page + 1 if page < all_page else 1
    try:
        await history(query, state, sessionmaker, current_page=page)
    except Exception as e:
        logger.exception(e)
        await query.answer("Страница всего одна :(")


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
            bot_id = data.get("bot_id")
            if bot_id:
                async with sessionmaker() as session:
                    await session.execute(
                        delete(Job).where(
                            (
                                and_(
                                    Job.bot_id == bot_id,
                                    Job.task == JobName.processed_users.value,
                                )
                            )
                        )
                    )
                    await session.commit()
            await query.message.edit_text(
                "Боты", reply_markup=await ik_action_with_bot()
            )
            await state.clear()
            await state.update_data(data)
        case "chat_add_or_delete":
            current_page = (await state.get_data())["current_page"]
            all_page = (await state.get_data())["all_page"]
            await query.message.edit_reply_markup(
                reply_markup=await ik_add_or_delete(
                    back_to="action_with_bot",
                    current_page=current_page,
                    all_page=all_page,
                ),
            )
        case "base_add_or_delete":
            current_page = (await state.get_data())["current_page"]
            all_page = (await state.get_data())["all_page"]
            await query.message.edit_reply_markup(
                reply_markup=await ik_add_or_delete(
                    current_page=current_page, all_page=all_page
                )
            )
        case "folders":
            await add_job_to_get_processed_users(
                query,
                state,
                sessionmaker,
                from_state=True,
            )


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
            if bot.name:
                continue
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
