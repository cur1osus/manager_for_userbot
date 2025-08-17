from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

import msgpack
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, MessageReactionUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.mysql.models import UserAnalyzed
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
