from aiogram import Router

from . import ban, getlog, reset, start, stat

router = Router()
router.include_routers(
    ban.router,
    start.router,
    reset.router,
    getlog.router,
    stat.router,
)
