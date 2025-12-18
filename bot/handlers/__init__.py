from aiogram import Router

from . import (antiflood_mode, back, bot_actions, bots, chats, cmds, folders,
               history, info, reaction, reg_userbot, user_per_minute)

router = Router()

router.include_routers(
    cmds.router,
    reg_userbot.router,
    bots.router,
    chats.router,
    info.router,
    history.router,
    user_per_minute.router,
    antiflood_mode.router,
    bot_actions.router,
    folders.router,
    back.router,
    reaction.router,
)
