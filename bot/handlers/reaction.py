from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Final

import msgpack
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, MessageReactionUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.mysql.models import BannedUser, UserAnalyzed, UserManager
from bot.keyboards.inline import (
    ik_tool_for_not_accepted_message,
)
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
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=None,
            )
            return

        user_a = await session.get(UserAnalyzed, id_for_db)
        if not user_a:
            await message.bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=None,
            )
            return

        d: dict = msgpack.unpackb(user_a.decision)
        raw_msg = user_a.additional_message
        t = await fn.short_view(user_a.id, d, raw_msg)

        await message.bot.edit_message_text(
            text=t,
            chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=None,
        )

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
        await message.bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=await ik_tool_for_not_accepted_message(),
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

    banned_users = await user.awaitable_attrs.banned_users
    data_to_add = await fn.collapse_repeated_data(
        [i.username for i in banned_users],
        [user_a.username],
    )
    banned_users.extend([BannedUser(username=i) for i in data_to_add])

    await session.commit()
    await query.message.edit_text(
        f"Пользователь @<b>{user_a.username}</b> заблокирован"
    )
    await asyncio.sleep(1.5)
    try:
        await query.message.delete()
    except:
        await query.message.reply("Сообщение устарело и не может быть удалено")
