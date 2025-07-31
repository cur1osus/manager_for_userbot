from aiogram import Router

from . import (
    back,
    bot_actions,
    bots,
    chats,
    cmds,
    folders,
    history,
    info,
    reg_userbot,
    user_per_minute,
)

router = Router()

router.include_routers(
    cmds.router,
    reg_userbot.router,
    bots.router,
    chats.router,
    info.router,
    history.router,
    user_per_minute.router,
    bot_actions.router,
    folders.router,
    back.router,
)
