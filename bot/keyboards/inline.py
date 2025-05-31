from aiogram.types import InlineKeyboardMarkup
from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.sqlite.models import Bot


async def ik_main_menu() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Боты", callback_data="bots")],
            [
                InlineKeyboardButton(
                    text="Добавить Нового Бота", callback_data="add_new_bot"
                )
            ],
        ]
    )
    return markup


async def ik_available_bots(bots_data: list[Bot]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if bots_data:
        for bot in bots_data:
            builder.button(text=bot.name, callback_data=f"bot_id:{bot.id}")
    builder.button(text="Назад", callback_data="back:to_main_menu")
    builder.adjust(1)
    return builder.as_markup()


async def ik_action_with_bot() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить", callback_data="delete")
    builder.button(text="Назад", callback_data="back:to_available_bots")
    builder.adjust(1)
    return builder.as_markup()
