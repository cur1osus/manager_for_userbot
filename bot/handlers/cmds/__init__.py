from aiogram import Router

from . import  start, reset

router = Router()
router.include_routers(
    start.router, reset.router
)
