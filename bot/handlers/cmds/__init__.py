from aiogram import Router

from . import ban, clear_analyzed, getlog, reset, start, stat

router = Router()
router.include_routers(
    ban.router,
    clear_analyzed.router,
    start.router,
    reset.router,
    getlog.router,
    stat.router,
)
