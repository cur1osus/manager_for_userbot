from aiogram import Router

from . import do, getlog, reset, start, stat, vu

router = Router()
router.include_routers(
    start.router,
    reset.router,
    getlog.router,
    vu.router,
    do.router,
    stat.router,
)
