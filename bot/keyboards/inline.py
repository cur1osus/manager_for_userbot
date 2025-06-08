from typing import Final

from aiogram.types import InlineKeyboardMarkup
from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.sqlite.models import Bot


async def ik_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Боты", callback_data="bots")],
            [
                InlineKeyboardButton(
                    text="Добавить Нового Бота", callback_data="add_new_bot"
                )
            ],
        ]
    )


async def ik_available_bots(bots_data: list[Bot]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if bots_data:
        for bot in bots_data:
            builder.button(text=bot.phone, callback_data=f"bot_id:{bot.id}")
    builder.button(text="Назад", callback_data="back:to_main_menu")
    builder.adjust(1)
    return builder.as_markup()


async def ik_action_with_bot() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить", callback_data="delete")
    builder.button(text="РеСтарт", callback_data="restart_bot")
    builder.button(text="Старт", callback_data="start")
    builder.button(text="Стоп", callback_data="stop")
    builder.button(text="Ответы", callback_data="info:answer")
    builder.button(text="Чаты", callback_data="info:chat")
    builder.button(text="Игноры", callback_data="info:ignore")
    builder.button(text="Баны", callback_data="info:ban")
    builder.button(text="Тригеры", callback_data="info:keyword")
    builder.button(text="<-", callback_data="back:to_available_bots")
    builder.adjust(1, 3, 2, 2, 1)
    return builder.as_markup()


async def ik_cancel_action() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
        ]
    )


async def ik_add_or_delete() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Удалить", callback_data="del")],
            [InlineKeyboardButton(text="Добавить", callback_data="add")],
            [InlineKeyboardButton(text="<-", callback_data="cancel")],
        ]
    )


limit_button: Final = 40


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
