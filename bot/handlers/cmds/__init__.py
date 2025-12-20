from aiogram import Router

from . import getlog, reset, start, stat

router = Router()
router.include_routers(
    start.router,
    reset.router,
    getlog.router,
    stat.router,
)
