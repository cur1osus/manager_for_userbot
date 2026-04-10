from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Final

import msgpack
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, MessageReactionUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import BannedUser, UserAnalyzed, UserManager
from bot.db.models import Bot as UserBot
from bot.keyboards.inline import ik_tool_for_not_accepted_message
from bot.utils import fn

if TYPE_CHECKING:
    pass

router = Router()
logger = logging.getLogger(__name__)

SUCCESS_EFFECT_IDS: Final[dict[str, str]] = {
    "5104841245755180586": "🔥",
    "5107584321108051014": "👍",
    "5044134455711629726": "❤️",
    "5046509860389126442": "🎉",
}


@router.message_reaction()
async def catching_reaction(
    message: MessageReactionUpdated,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if not message.new_reaction:
        data_state = await state.get_data()
        id_for_db = data_state.get(f"rmsg_{message.message_id}")

        if not id_for_db:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=None,
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise
            return

        user_a = await session.get(UserAnalyzed, id_for_db)
        if not user_a:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=None,
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e):
                    raise
            return

        d: dict = msgpack.unpackb(user_a.decision)
        raw_msg = user_a.additional_message

        userbot: UserBot = await user_a.awaitable_attrs.bot
        t = await fn.short_view(user_a.id, userbot.name, d, raw_msg)

        try:
            await message.bot.edit_message_text(
                text=t,
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=None,
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise

        del data_state[f"rmsg_{message.message_id}"]
        await state.set_data(data_state)

        return

    if message.new_reaction[0].emoji == "🔥":
        try:
            await message.bot.delete_message(message.chat.id, message.message_id)
        except:
            await message.bot.send_message(
                message.chat.id, "Сообщение устарело и не может быть удалено"
            )
    else:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=await ik_tool_for_not_accepted_message(),
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise


@router.callback_query(F.data == "in_the_trash")
async def in_the_trash(query: CallbackQuery) -> None:
    try:
        await query.message.delete()
    except Exception:
        await query.answer(
            text="Сообщение устарело и не может быть удалено",
            show_alert=True,
        )


@router.callback_query(F.data == "view_full_message")
async def tool_view_message(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    t = query.message.text
    if not t:
        await query.answer("Не найдено сообщение", show_alert=True)
        return
    id_for_db = fn.get_id_from_message(t)
    if not id_for_db:
        await query.answer("Не найдено ID сообщения", show_alert=True)
        return

    user_a = await session.get(UserAnalyzed, id_for_db)
    if not user_a:
        await query.answer("Не найдена запись", show_alert=True)
        return

    d: dict = msgpack.unpackb(user_a.decision)
    raw_msg = user_a.additional_message
    t = await fn.long_view(user_a.id, d, raw_msg)
    await query.message.edit_text(
        t, reply_markup=await ik_tool_for_not_accepted_message()
    )

    await state.update_data({f"rmsg_{query.message.message_id}": user_a.id})


@router.callback_query(F.data == "send_message")
async def tool_send_message(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    t = query.message.text
    if not t:
        await query.answer("Не найдено сообщение", show_alert=True)
        return
    id_for_db = fn.get_id_from_message(t)
    if not id_for_db:
        await query.answer("Не найдено ID сообщения", show_alert=True)
        return
    user_a = await session.get(UserAnalyzed, id_for_db)
    if not user_a:
        await query.answer("Не найдена запись", show_alert=True)
        return

    user_a.accepted = True

    d: dict = msgpack.unpackb(user_a.decision)
    raw_msg = user_a.additional_message
    t = await fn.long_view(user_a.id, d, raw_msg)
    t += "\n<b>Сообщение поставлено в очередь на отправку ✅</b>"

    await query.message.edit_text(t, reply_markup=None)
    await session.commit()


@router.callback_query(F.data == "send_messages")
async def tool_send_messages(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: UserManager,
) -> None:
    t = query.message.text
    if not t:
        await query.answer("Не найдено сообщение", show_alert=True)
        return

    user.is_antiflood_mode = False
    await session.commit()

    t += "\n\n<b>Отправка сообщений возобновлена, flood mode выключен ✅</b>"

    await query.message.edit_text(t, reply_markup=None)


@router.callback_query(F.data == "ban_user")
async def tool_ban_user(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    t = query.message.text
    if not t:
        await query.answer("Не найдено сообщение", show_alert=True)
        return
    id_for_db = fn.get_id_from_message(t)
    if not id_for_db:
        await query.answer("Не найдено ID сообщения", show_alert=True)
        return
    user_a = await session.get(UserAnalyzed, id_for_db)
    if not user_a:
        await query.answer("Не найдена запись", show_alert=True)
        return

    username = (
        f"@{user_a.username}"
        if not user_a.username.startswith("@")
        else user_a.username
    )
    banned_users = await user.awaitable_attrs.banned_users
    data_to_add = await fn.collapse_repeated_data(
        [i.username for i in banned_users],
        [username],
    )
    banned_users.extend([BannedUser(username=i) for i in data_to_add])

    await session.commit()
    await query.message.edit_text(
        f"Пользователь <b>@{user_a.username}</b> заблокирован"
    )
    await asyncio.sleep(1.5)
    try:
        await query.message.delete()
    except:
        await query.message.reply("Сообщение устарело и не может быть удалено")
