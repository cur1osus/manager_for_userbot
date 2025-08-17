from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.mysql.models import (
    UserAnalyzed,
    UserManager,
)
from bot.keyboards.factories import ArrowHistoryFactory
from bot.keyboards.inline import (
    ik_back,
    ik_history_back,
)
from bot.utils import fn

if TYPE_CHECKING:
    from redis.asyncio import Redis

router = Router()
logger = logging.getLogger(__name__)
q_string_per_page = 15


@router.callback_query(F.data == "history")
async def history(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
    current_page: int | None = None,
) -> None:
    len_data = await session.scalar(
        select(func.count(UserAnalyzed.id)).where(
            and_(
                UserAnalyzed.accepted.is_(True),
                UserAnalyzed.sended.is_(True),
            )
        )
    )
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
            .where(
                and_(
                    UserAnalyzed.sended.is_(True),
                    UserAnalyzed.accepted.is_(True),
                )
            )
            .order_by(UserAnalyzed.id.asc())
            .slice(
                (current_page - 1) * q_string_per_page,
                current_page * q_string_per_page,
            )
        )
    ).all()  # pyright: ignore
    t = ""
    start_for_index = ((current_page - 1) * q_string_per_page) + 1
    for index, _user in enumerate(user_analyzed, start=start_for_index):
        msg = _user.additional_message[:10].replace("\n", "")
        t += f"{index}. {f'[{_user.bot_id}]' if _user.bot_id else ''} @{_user.username} {msg}...\n"
    if len(t) > fn.max_length_message:
        t = t[: fn.max_length_message - 4]
        t += "..."
    await state.update_data(
        current_page_history=current_page, all_page_history=all_page
    )
    await query.message.edit_text(
        text=t,
        reply_markup=await ik_history_back(
            all_page=all_page,
            current_page=current_page,
        ),
    )


@router.callback_query(ArrowHistoryFactory.filter())
async def arrow_history(
    query: CallbackQuery,
    callback_data: ArrowHistoryFactory,
    user: UserManager,
    redis: Redis,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    arrow = callback_data.to
    data = await state.get_data()
    page = data["current_page_history"]
    all_page = data["all_page_history"]
    match arrow:
        case "left":
            page = page - 1 if page > 1 else all_page
        case "right":
            page = page + 1 if page < all_page else 1
    try:
        await history(query, user, state, session, current_page=page)
    except Exception as e:
        logger.exception(e)
        await query.answer("Страница всего одна :(")
