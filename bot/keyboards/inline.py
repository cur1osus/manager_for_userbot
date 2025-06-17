import logging
from typing import Final

from aiogram.types import InlineKeyboardMarkup
from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.mysql.models import Bot

logger = logging.getLogger(__name__)


async def ik_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Боты", callback_data="bots")
    builder.button(text="❇️ Добавить бота", callback_data="add_new_bot")
    builder.button(text="❌ Игноры", callback_data="info:ignore")
    builder.button(text="🚷 Баны", callback_data="info:ban")
    builder.button(text="❗️Тригеры", callback_data="info:keyword")
    builder.button(text="🗣 Ответы", callback_data="info:answer")
    builder.button(
        text="🏃🏼‍➡️ Пропускная способность", callback_data="users_per_minute"
    )
    builder.button(text="🔍 История", callback_data="history")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


async def ik_available_bots(
    bots_data: list[Bot], back_to: str = "default"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if bots_data:
        for bot in bots_data:
            builder.button(
                text=f"{'🟢' if bot.is_started else '🔴'} {bot.phone} ({bot.name or 'имя загружается...'})",
                callback_data=f"bot_id:{bot.id}",
            )
    builder.button(text="<-", callback_data=f"back:{back_to}")
    builder.adjust(1)
    return builder.as_markup()


async def ik_action_with_bot(back_to: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить", callback_data="delete")
    builder.button(text="🔄 РеСтарт", callback_data="restart_bot")
    builder.button(text="🟢 Старт", callback_data="start")
    builder.button(text="🔴 Стоп", callback_data="stop")
    builder.button(text="💬 Чаты", callback_data="info:chat")
    builder.button(
        text="🧠 Получить Обработанных",
        callback_data="processed_users",
    )
    builder.button(text="<-", callback_data=f"back:{back_to}")
    builder.adjust(1, 3, 1, 1)
    return builder.as_markup()


async def ik_cancel_action(back_to: str = "default") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Отмена", callback_data=f"cancel:{back_to}")],
        ]
    )


async def ik_add_or_delete(back_to: str = "default") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➖ Удалить", callback_data="del")],
            [InlineKeyboardButton(text="➕ Добавить", callback_data="add")],
            [InlineKeyboardButton(text="<-", callback_data=f"back:{back_to}")],
        ]
    )


limit_button: Final = 80


async def ik_num_matrix_del(
    ids: list[str], back_to: str = "default"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = 0
    if len(ids) > limit_button:
        start = len(ids) - limit_button
        ids = ids[start:]
    for ind, id in enumerate(ids, start):
        builder.button(text=str(ind + 1), callback_data=f"del:{id}")
    builder.button(text="<-", callback_data=f"back:{back_to}")
    builder.adjust(5)
    return builder.as_markup()


max_users_per_minute: Final = 30


async def ik_num_matrix_users(current_choose: int, back_to: str = "default"):
    builder = InlineKeyboardBuilder()
    for i in range(1, max_users_per_minute + 1):
        if current_choose == i:
            builder.button(text=f"{i}🔘", callback_data=f"upm:{i}")
            continue
        builder.button(text=str(i), callback_data=f"upm:{i}")
    builder.button(text="<-", callback_data=f"back:{back_to}")
    builder.adjust(5)
    return builder.as_markup()


async def ik_get_processed_users(back_to: str = "default"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Получить обработанных", callback_data="get_processed_users"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"back:{back_to}",
                )
            ],
        ]
    )


async def ik_reload_processed_users(back_to: str = "default"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Обновить список обработанных",
                    callback_data="update_processed_users",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"back:{back_to}",
                )
            ],
        ]
    )


async def ik_back(back_to: str = "default"):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"back:{back_to}",
                )
            ],
        ]
    )
