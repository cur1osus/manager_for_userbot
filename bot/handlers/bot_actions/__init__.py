from __future__ import annotations

from aiogram import Router

from . import connect, delete, disconnect, lifecycle, navigation, select_bot

router = Router()

router.include_routers(
    select_bot.router,
    connect.router,
    lifecycle.router,
    disconnect.router,
    delete.router,
    navigation.router,
)
