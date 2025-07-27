from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

import msgpack  # type: ignore
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import and_, asc, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
    ik_connect_bot,
    ik_folders,
    ik_folders_with_users,
    ik_history_back,
    ik_main_menu,
    ik_num_matrix_del,
    ik_num_matrix_users,
    ik_processed_users,
)
from bot.states import UserState
from bot.utils import fn
from bot.utils.manager import bot_has_started, delete_bot, start_bot
from config import path_to_folder, sep

if TYPE_CHECKING:
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.split(":")[0] == "bot_id")
async def manage_bot(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = int(query.data.split(":")[1])

    bot = await user.get_obj_bot(bot_id)
    if not bot:
        await query.message.edit_text(text="Нет доступа", reply_markup=await ik_back())
        return
    await state.update_data(bot_id=bot_id)
    if bot.is_connected:
        await query.message.edit_text(
            "Выберите действие",
            reply_markup=await ik_action_with_bot(back_to="bots"),
        )
    else:
        await query.message.edit_text(
            "Выберите действие",
            reply_markup=await ik_connect_bot(back_to="bots"),
        )


@router.callback_query(F.data == "connect")
async def connect_bot(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = (await state.get_data()).get("bot_id")
    if not bot_id:
        await query.message.edit_text(text="bot_id пустой")
        return
    bot = await user.get_obj_bot(bot_id)
    phone_code_hash = await fn.send_code_via_telethon(
        bot.phone,
        bot.api_id,
        bot.api_hash,
        bot.path_session,
    )
    if phone_code_hash is None:
        await query.message.answer("Ошибка при отправке кода", reply_markup=None)
        return
    await state.update_data(
        api_id=bot.api_id,
        api_hash=bot.api_hash,
        phone=bot.phone,
        phone_code_hash=phone_code_hash,
        path_session=bot.path_session,
        save_bot=False,
    )
    await query.message.edit_text("Введите code", reply_markup=None)
    await state.set_state(UserState.enter_code)


@router.callback_query(F.data == "restart_bot")
async def restart_bot(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = (await state.get_data())["bot_id"]
    bot: Bot | None = await user.get_obj_bot(bot_id)
    if not bot:
        return

    phone = bot.phone
    await delete_bot(phone, path_to_folder)
    asyncio.create_task(start_bot(phone, path_to_folder))
    await query.message.edit_text(
        "Бот подключен и запущен", reply_markup=await ik_main_menu()
    )


@router.callback_query(F.data == "start")
async def start_bot_process(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = (await state.get_data())["bot_id"]
    bot: Bot | None = await user.get_obj_bot(bot_id)
    bot.is_started = True
    await session.commit()
    await query.message.edit_text(
        "Бот Начал писать и анализировать сообщения 🟢",
        reply_markup=await ik_action_with_bot(),
    )


@router.callback_query(F.data == "stop")
async def stop_bot_process(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    bot_id = (await state.get_data())["bot_id"]
    bot: Bot | None = await user.get_obj_bot(bot_id)
    bot.is_started = False
    await session.commit()
    await query.message.edit_text(
        "Бот остановлен и не будет писать и анализировать сообщения 🔴",
        reply_markup=await ik_action_with_bot(),
    )


@router.callback_query(F.data == "disconnected")
async def disconnected_bot_(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    bot_id = data["bot_id"]
    bot: Bot | None = await user.get_obj_bot(bot_id)
    if bot is None:
        return
    bot.is_connected = False
    bot.is_started = False
    await delete_bot(phone=bot.phone, path_to_folder=path_to_folder)
    await session.commit()
    await query.message.edit_text("Бот отключен", reply_markup=await ik_main_menu())


@router.callback_query(F.data == "delete")
async def delete_bot_(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    bot_id = data["bot_id"]
    bot: Bot | None = await user.get_obj_bot(bot_id)
    if bot is None:
        return
    user.bots.remove(bot)
    await delete_bot(phone=bot.phone, path_to_folder=path_to_folder)
    await session.commit()
    await state.clear()
    await query.message.edit_text("Бот удален", reply_markup=await ik_main_menu())


@router.callback_query(F.data.split(":")[0] == "info")
async def info(
    query: CallbackQuery | Message,
    user: UserManager,
    state: FSMContext,
    sessionmaker: async_sessionmaker | None = None,
    type_data: str | None = None,
    current_page: int | None = None,
) -> None:
    if isinstance(query, CallbackQuery):
        type_data = type_data or query.data.split(":")[1]
    if sessionmaker:
        async with sessionmaker() as session:
            user = await session.get(UserManager, user.id)

    await state.set_state(UserState.action)

    kwargs_for_keyboard: dict[str, Any] = {}
    all_page = None
    data_str = None
    data = []
    match type_data:
        case "answer":
            data = [i.sentence for i in user.messages_to_answer]
            data_str = None if data else "Ответы отсутствуют"
        case "ban":
            data = [i.username for i in user.banned_users]
            data_str = None if data else "Пользователи отсутствуют"
        case "chat":
            bot_id = (await state.get_data())["bot_id"]
            data = (await user.get_obj_bot(bot_id)).chats
            q_string_per_page = 10
            all_page = await fn.count_page(
                len_data=len(data), q_string_per_page=q_string_per_page
            )
            current_page = current_page or all_page
            data_str = (
                await fn.watch_data_chats(
                    data,
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
            data = [i.word for i in user.keywords]
            data_str = None if data else "Триггерные слова отсутствуют"

        case "ignore":
            data = [i.word for i in user.ignored_words]
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
            current_page,
        )
    all_page = all_page or 1
    current_page = current_page or 1
    kwargs_for_keyboard["all_page"] = all_page
    kwargs_for_keyboard["current_page"] = current_page
    if isinstance(query, CallbackQuery):
        await query.message.edit_text(
            text=data_str,
            reply_markup=await ik_add_or_delete(**kwargs_for_keyboard),
        )
    else:
        msg = await query.answer(
            text=data_str,
            reply_markup=await ik_add_or_delete(**kwargs_for_keyboard),
        )
        await fn.set_general_message(state, msg)
    await state.update_data(
        type_data=type_data,
        current_page=current_page,
        all_page=all_page,
    )


@router.callback_query(F.data.in_(["arrow_left", "arrow_right"]))
async def arrow(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
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
        await info(query, user, state, type_data=type_data, current_page=page)
    except Exception:
        await query.answer("Страница всего одна :(")


@router.callback_query(UserState.action, F.data == "add")
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
        case "chat":
            bot_id = (await state.get_data())["bot_id"]
            bot = await user.get_obj_bot(bot_id)
            chats = await bot.awaitable_attrs.chats
            data_to_add = await fn.collapse_repeated_data(
                [i.chat_id for i in chats], data_to_add
            )
            chats.extend([MonitoringChat(chat_id=i) for i in data_to_add])
            job = Job(task=JobName.get_chat_title.value, bot=bot)
            session.add(job)
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
    await info(
        message,
        user,
        state,
        type_data=type_data,
        current_page=current_page,
    )


@router.callback_query(UserState.action, F.data == "del")
async def delete_(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
    sessionmaker: async_sessionmaker | None = None,
) -> None:
    type_data = (await state.get_data())["type_data"]
    kwargs_for_keyboard: dict[str, str] = {"back_to": "base_add_or_delete"}
    ids = []
    if sessionmaker:
        async with sessionmaker() as session:
            user = await session.get(UserManager, user.id)
    match type_data:
        case "answer":
            ids = [i.id for i in user.messages_to_answer]
        case "ban":
            ids = [i.id for i in user.banned_users]
        case "chat":
            bot_id = (await state.get_data())["bot_id"]
            bot = await user.get_obj_bot(bot_id)
            ids = [i.id for i in bot.chats]
            kwargs_for_keyboard["back_to"] = "chat_add_or_delete"
        case "ignore":
            ids = [i.id for i in user.ignored_words]
        case "keyword":
            ids = [i.id for i in user.keywords]
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
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker,
) -> None:
    type_data = (await state.get_data())["type_data"]
    id_ = int(query.data.split(":")[1])
    obj = None
    match type_data:
        case "answer":
            obj = await session.get(MessageToAnswer, id_)
        case "ban":
            obj = await session.get(BannedUser, id_)
        case "chat":
            obj = await session.get(MonitoringChat, id_)
        case "ignore":
            obj = await session.get(IgnoredWord, id_)
        case "keyword":
            obj = await session.get(KeyWord, id_)
    await session.delete(obj)
    await session.commit()
    await info(query, user, state, sessionmaker=sessionmaker, type_data=type_data)
    await delete_(query, user, state, sessionmaker=sessionmaker)


@router.callback_query(F.data == "users_per_minute")
async def users_per_minute(
    query: CallbackQuery,
    user: UserManager,
) -> None:
    try:
        await query.message.edit_text(
            text="Выбери пропускную способность:",
            reply_markup=await ik_num_matrix_users(user.users_per_minute),
        )
    except Exception:
        logger.exception("not modified message")


@router.callback_query(F.data.split(":")[0] == "upm")
async def change_users_per_minute(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    upm = int(query.data.split(":")[1])
    user.users_per_minute = upm
    user = await session.merge(user)
    await session.commit()
    try:
        await users_per_minute(query, user)
    except Exception:
        logger.exception("not modified message")


@router.callback_query(F.data == "processed_users")
async def add_job_to_get_processed_users(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker,
    from_state: bool = False,
) -> None:
    await state.set_state(UserState.action)

    bot_id = (await state.get_data())["bot_id"]
    bot = await user.get_obj_bot(bot_id)
    job = Job(task=JobName.get_folders.value)
    bot.jobs.append(job)
    await session.commit()

    switch = True
    tries = 0
    while switch:
        await query.message.edit_text(text="Получаю названия папок", reply_markup=None)
        async with sessionmaker() as session:
            job: Job | None = await session.scalar(
                select(Job)
                .where(
                    and_(
                        Job.bot_id == bot_id,
                        Job.task == JobName.get_folders.value,
                    )
                )
                .order_by(Job.id.desc())
                .limit(1)
            )
        sleep_sec = 0.5
        await asyncio.sleep(sleep_sec)
        await query.message.edit_text(
            text="Получаю названия папок 🌥", reply_markup=None
        )
        await asyncio.sleep(sleep_sec)
        await query.message.edit_text(text="Получаю названия папок 🌥⛅️")
        await asyncio.sleep(sleep_sec)
        await query.message.edit_text(text="Получаю названия папок 🌥⛅️🌤")
        await asyncio.sleep(sleep_sec)
        await query.message.edit_text(text="Получаю названия папок 🌥⛅️🌤☀️")
        await asyncio.sleep(sleep_sec)
        if job and job.answer:
            switch = False
        if tries > 3:
            await query.message.edit_text(
                text="Не смог получить папки",
                reply_markup=await ik_back(back_to="action_with_bot"),
            )
            return
        tries += 1

    raw_folders: list[dict[str, str]] = msgpack.unpackb(job.answer)
    name_folders = [i["name"] for i in raw_folders]
    choice_folders = {i: True for i in name_folders}

    await state.update_data(choice_folders=choice_folders, raw_folders=raw_folders)
    await query.message.edit_text(
        text="Папки",
        reply_markup=await ik_folders(choice_folders, back_to="action_with_bot"),
    )


@router.callback_query(UserState.action, F.data.split(":")[0] == "folder")
async def choice_folder(
    query: CallbackQuery, user: UserManager, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    target_folder = query.data.split(":")[1]
    choice_folders = data["choice_folders"]
    choice_folders[target_folder] = not choice_folders[target_folder]
    await state.update_data(choice_folders=choice_folders)
    await query.message.edit_text(
        text="Папки",
        reply_markup=await ik_folders(choice_folders, back_to="action_with_bot"),
    )


@router.callback_query(UserState.action, F.data.split(":")[0] == "accept_folders")
async def get_processed_users_from_folder(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker,
    from_state: bool | None = None,
) -> None:
    data = await state.get_data()
    if from_state:
        folders = data.get("folders", [])
        name_folders = [i["name"] for i in folders]
    else:
        choice_folders: dict[str, bool] = data["choice_folders"]
        raw_folders: list[dict[str, str]] = data["raw_folders"]
        folders = [
            raw_folder
            for raw_folder in raw_folders
            if choice_folders[raw_folder["name"]]
        ]  # pyright: ignore

        bot_id = data["bot_id"]
        bot = await user.get_obj_bot(bot_id)
        job = Job(
            task=JobName.processed_users.value, task_metadata=msgpack.packb(folders)
        )
        bot.jobs.append(job)
        await session.commit()

        switch = True
        tries = 0
        while switch:
            await query.message.edit_text(text="Получаю папки", reply_markup=None)
            async with sessionmaker() as session:
                sleep_sec = 0.5
                await asyncio.sleep(sleep_sec)
                await query.message.edit_text(
                    text="Получаю папки 😐", reply_markup=None
                )
                await asyncio.sleep(sleep_sec)
                await query.message.edit_text(text="Получаю папки 😐🙂")
                await asyncio.sleep(sleep_sec)
                await query.message.edit_text(text="Получаю папки 😐🙂😁")
                await asyncio.sleep(sleep_sec)
                await query.message.edit_text(text="Получаю папки 😐🙂😁😆")
                await asyncio.sleep(sleep_sec)
                job: Job | None = await session.scalar(
                    select(Job)
                    .where(
                        and_(
                            Job.bot_id == bot_id,
                            Job.task == JobName.processed_users.value,
                        )
                    )
                    .order_by(Job.id.desc())
                    .limit(1)
                )

            if job and job.answer:
                switch = False
            if tries > 3:
                await query.message.edit_text(
                    text="Не смог получить папки",
                    reply_markup=await ik_back(back_to="action_with_bot"),
                )
                return
            tries += 1
        folders: list[dict[str, list[dict[str, Any]] | str]] = msgpack.unpackb(
            job.answer
        )
        name_folders = [i["name"] for i in folders]
        await state.update_data(folders=folders)
    await query.message.edit_text(
        text="Папки",
        reply_markup=await ik_folders_with_users(
            name_folders,  # pyright: ignore
            back_to="action_with_bot",
        ),
    )


@router.callback_query(UserState.action, F.data.split(":")[0] == "target_folder")
async def view_target_folder(
    query: CallbackQuery, state: FSMContext, current_page: int | None = None
) -> None:
    data = await state.get_data()
    if current_page:
        folder = data["current_folder"]
    else:
        target_folder = query.data.split(":")[1]
        folders: list[dict[str, dict[str, Any] | str]] = data["folders"]
        folder = next(i for i in folders if i["name"] == target_folder)
    page = current_page or 1
    q_string_per_page = 10
    formatting_choices = data.get("formatting_choices", [True, True, False])
    all_page = await fn.count_page(
        len(folder.get("pinned_peers", [])), q_string_per_page
    )
    t = await fn.watch_processed_users(
        folder.get("pinned_peers"),  # pyright: ignore
        sep,
        q_string_per_page,
        page,
        formatting_choices,
    )
    await state.update_data(
        current_page=page,
        all_page=all_page,
        current_folder=folder,
        formatting_choices=formatting_choices,
    )
    if not t:
        t = "Папка пустая :("
    await query.message.edit_text(
        t,
        reply_markup=await ik_processed_users(
            all_page=all_page,
            current_page=page,
            choices=formatting_choices,
            back_to="accept_folders",
        ),
    )


@router.callback_query(UserState.action, F.data.split(":")[0] == "u")
async def arrow_processed_users(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
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
        await view_target_folder(query, state, current_page=page)
    except Exception as e:
        logger.exception(e)
        await query.answer("Страница всего одна :(")


@router.callback_query(
    UserState.action, F.data.in_(["f_username", "f_first_name", "f_copy"])
)
async def formatting_(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    formatting_choices: list[bool] = data["formatting_choices"]
    if query.data == "f_first_name":
        formatting_choices[0] = not formatting_choices[0]
    elif query.data == "f_username":
        formatting_choices[1] = not formatting_choices[1]
    elif query.data == "f_copy":
        formatting_choices[2] = not formatting_choices[2]
    if formatting_choices[0] is False and formatting_choices[1] is False:
        formatting_choices[0] = True
    await state.update_data(formatting_choices=formatting_choices)
    with contextlib.suppress(Exception):
        await view_target_folder(query, state, current_page=data["current_page"])


@router.callback_query(F.data == "history")
async def history(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
    current_page: int | None = None,
) -> None:
    q_string_per_page = 15
    len_data = await session.scalar(select(func.count(UserAnalyzed.id)))
    if not len_data:
        await query.message.edit_text(
            text="История пуста", reply_markup=await ik_back()
        )
        return
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
    ).all()  # pyright: ignore
    t = ""
    for _user in user_analyzed:
        msg = _user.additional_message[:10].replace("\n", "")
        if not _user.sended:
            continue
        t += f"{_user.id}. {f'[{_user.bot_id}/]' if _user.bot_id else ''} @{_user.username} {msg}...\n"
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
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
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
        await history(query, user, state, session, current_page=page)
    except Exception as e:
        logger.exception(e)
        await query.answer("Страница всего одна :(")


@router.callback_query(UserState.action, F.data.split(":")[0] == "cancel")
async def cancel_action_chat_add_or_delete(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    to = query.data.split(":")[1]
    type_data = (await state.get_data())["type_data"]
    match to:
        case "default":
            await info(query, user, state, type_data=type_data)
        case "add_or_delete":
            await info(query, user, state, type_data=type_data)


@router.callback_query(UserState.action, F.data.split(":")[0] == "back")
async def back_action(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker,
) -> None:
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
            current_page = (await state.get_data()).get("current_page", 1)
            all_page = (await state.get_data()).get("all_page", 1)
            await query.message.edit_reply_markup(
                reply_markup=await ik_add_or_delete(
                    back_to="action_with_bot",
                    current_page=current_page,
                    all_page=all_page,
                ),
            )
        case "base_add_or_delete":
            data = await state.get_data()
            current_page = (await state.get_data()).get("current_page", 1)
            all_page = (await state.get_data()).get("all_page", 1)
            await query.message.edit_reply_markup(
                reply_markup=await ik_add_or_delete(
                    current_page=current_page, all_page=all_page
                )
            )
        case "folders":
            await add_job_to_get_processed_users(
                query,
                user,
                state,
                session,
                sessionmaker,
                from_state=True,
            )
        case "accept_folders":
            await get_processed_users_from_folder(
                query, user, state, session, sessionmaker, from_state=True
            )


@router.callback_query(F.data == "bots")
async def show_bots(
    query: CallbackQuery,
    session: AsyncSession,
) -> None:
    bots_data: list[Bot] = (await session.scalars(select(Bot))).all()  # pyright: ignore
    if not bots_data:
        await query.message.edit_text(
            text="У вас нет ботов", reply_markup=await ik_back()
        )
        return
    for bot in bots_data:
        r = await bot_has_started(bot.phone, path_to_folder)
        bot.is_connected = r
        if r:
            job = Job(task=JobName.get_me_name.value)
            bot.jobs.append(job)
    await session.commit()
    await query.message.edit_text(
        "Боты",
        reply_markup=await ik_available_bots(bots_data),
    )


@router.callback_query(F.data.split(":")[0] == "back")
async def back(
    query: CallbackQuery,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    to = query.data.split(":")[1]
    match to:
        case "default":
            await query.message.edit_text(
                text="Главное меню", reply_markup=await ik_main_menu()
            )
        case "bots":
            await query.message.edit_text(
                "Боты", reply_markup=await ik_available_bots(user.bots)
            )
