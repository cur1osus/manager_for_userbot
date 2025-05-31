from aiogram import Router

from . import  cmds

router = Router()

router.include_routers(
    cmds.router
)
