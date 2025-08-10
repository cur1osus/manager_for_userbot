from aiogram import Router

from . import start, reset, getlog, vu, do

router = Router()
router.include_routers(
    start.router,
    reset.router,
    getlog.router,
    vu.router,
    do.router,
)
