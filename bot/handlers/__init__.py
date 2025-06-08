from aiogram import Router

from . import cmds, actions, reg_userbot

router = Router()

router.include_routers(
    cmds.router,
    actions.router,
    reg_userbot.router,
)
