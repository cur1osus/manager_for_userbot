from aiogram import Router

from . import ban, clear_analyzed, delete_sessions, getlog, reset, start, stat

router = Router()
router.include_routers(
    ban.router,
    clear_analyzed.router,
    delete_sessions.router,
    start.router,
    reset.router,
    getlog.router,
    stat.router,
)
