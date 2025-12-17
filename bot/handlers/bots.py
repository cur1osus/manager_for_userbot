from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.mysql.models import (
    Job,
    JobName,
    UserManager,
)
from bot.keyboards.inline import (
    ik_available_bots,
    ik_back,
)
from bot.utils import fn

if TYPE_CHECKING:
    pass

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "bots")
async def show_bots(
    query: CallbackQuery,
    user: UserManager,
    session: AsyncSession,
) -> None:
    bots = await user.awaitable_attrs.bots
    if not bots:
        await query.message.edit_text(
            text="У вас нет ботов", reply_markup=await ik_back()
        )
        return
    for bot in bots:
        r = await fn.Manager.bot_run(bot.phone)
        bot.is_connected = r
        if r:
            job = Job(task=JobName.get_me_name.value)
            bot.jobs.append(job)
    await session.commit()
    await query.message.edit_text(
        "Боты",
        reply_markup=await ik_available_bots(bots),
    )
