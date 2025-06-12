from aiogram import Router

from . import start, reset, getlog

router = Router()
router.include_routers(start.router, reset.router, getlog.router)
