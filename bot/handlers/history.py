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
ROWS_PER_PAGE = 15
HISTORY_FILTER = (
    UserAnalyzed.accepted.is_(True),
    UserAnalyzed.sended.is_(True),
)


def _normalize_page(page: int, total_pages: int) -> int:
    if page < 1:
        return 1
    if page > total_pages:
        return total_pages
    return page


def _build_history_text(users: list[UserAnalyzed], start_index: int) -> str:
    rows = []
    for index, user in enumerate(users, start=start_index):
        preview = user.additional_message.replace("\n", " ")
        preview = f"{preview[:10]}..." if len(preview) > 10 else preview
        bot_tag = f"[{user.bot_id}]" if user.bot_id else ""
        username = user.username or "без username"
        line = " ".join(
            part for part in (f"{index}.", bot_tag, username, preview) if part
        )
        rows.append(line)

    text = "\n".join(rows)
    if len(text) > fn.max_length_message:
        text = text[: fn.max_length_message - 3] + "..."
    return text


@router.callback_query(F.data == "history")
async def history(
    query: CallbackQuery,
    user: UserManager,
    state: FSMContext,
    session: AsyncSession,
    current_page: int | None = None,
) -> None:
    rows_count = await session.scalar(
        select(func.count(UserAnalyzed.id)).where(and_(*HISTORY_FILTER))
    )
    if not rows_count:
        await query.message.edit_text(
            text="История пуста", reply_markup=await ik_back()
        )
        return

    all_page = await fn.count_page(rows_count, ROWS_PER_PAGE)
    current_page = _normalize_page(current_page or all_page, all_page)
    user_analyzed: list[UserAnalyzed] = (
        await session.scalars(
            select(UserAnalyzed)
            .where(and_(*HISTORY_FILTER))
            .order_by(UserAnalyzed.id.asc())
            .offset((current_page - 1) * ROWS_PER_PAGE)
            .limit(ROWS_PER_PAGE)
        )
    ).all()  # pyright: ignore
    text = _build_history_text(
        user_analyzed, start_index=((current_page - 1) * ROWS_PER_PAGE) + 1
    )
    await state.update_data(
        current_page_history=current_page, all_page_history=all_page
    )
    await query.message.edit_text(
        text=text,
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
    page = data.get("current_page_history")
    all_page = data.get("all_page_history")

    if not page or not all_page:
        await query.answer("История недоступна, откройте её заново.", show_alert=True)
        return
    if all_page <= 1:
        await query.answer("Страница всего одна :(", show_alert=True)
        return

    match arrow:
        case "left":
            page = page - 1 if page > 1 else all_page
        case "right":
            page = page + 1 if page < all_page else 1
        case _:
            await query.answer("Неизвестное действие.")
            return

    try:
        await history(query, user, state, session, current_page=page)
    except Exception:
        logger.exception("Failed to show history page %s", page)
        await query.answer("Не удалось обновить историю.", show_alert=True)
