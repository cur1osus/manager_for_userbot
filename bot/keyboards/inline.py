from typing import Final

from aiogram.types import InlineKeyboardMarkup
from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.sqlite.models import Bot
import logging

logger = logging.getLogger(__name__)


async def ik_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Боты", callback_data="bots")
    builder.button(text="Добавить бота", callback_data="add_new_bot")
    builder.button(text="Игноры", callback_data="info:ignore")
    builder.button(text="Баны", callback_data="info:ban")
    builder.button(text="Тригеры", callback_data="info:keyword")
    builder.button(text="Ответы", callback_data="info:answer")
    builder.adjust(2)
    return builder.as_markup()


async def ik_available_bots(bots_data: list[Bot]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if bots_data:
        for bot in bots_data:
            builder.button(text=bot.phone, callback_data=f"bot_id:{bot.id}")
    builder.button(text="<-", callback_data="back:to_main_menu")
    builder.adjust(1)
    return builder.as_markup()


async def ik_action_with_bot() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить", callback_data="delete")
    builder.button(text="РеСтарт", callback_data="restart_bot")
    builder.button(text="Старт", callback_data="start")
    builder.button(text="Стоп", callback_data="stop")
    builder.button(text="Чаты", callback_data="info:chat")
    builder.button(text="<-", callback_data="back:to_available_bots")
    builder.adjust(1, 3, 1, 1)
    return builder.as_markup()


async def ik_cancel_action(additional_callback: str = "") -> InlineKeyboardMarkup:
    if additional_callback:
        additional_callback = f":{additional_callback}"
    if len(additional_callback) > 54:
        logger.info(f"Слишком большая дата для добавления: {additional_callback}")
        additional_callback = ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Отмена", callback_data=f"cancel{additional_callback}"
                )
            ],
        ]
    )


async def ik_add_or_delete(additional_callback: str = "") -> InlineKeyboardMarkup:
    if additional_callback:
        additional_callback = f":{additional_callback}"
    if len(additional_callback) > 54:
        logger.info(f"Слишком большая дата для добавления: {additional_callback}")
        additional_callback = ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Удалить", callback_data="del")],
            [InlineKeyboardButton(text="Добавить", callback_data="add")],
            [
                InlineKeyboardButton(
                    text="<-", callback_data=f"cancel{additional_callback}"
                )
            ],
        ]
    )


limit_button: Final = 80


async def ik_num_matrix(ids: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = 0
    if len(ids) > limit_button:
        start = len(ids) - limit_button
        ids = ids[start:]
    for ind, id in enumerate(ids, start):
        builder.button(text=str(ind + 1), callback_data=f"del:{id}")
    builder.button(text="<-", callback_data="back:to_add_or_delete")
    builder.adjust(5)
    return builder.as_markup()
