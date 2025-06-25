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
    # builder.button(text="🔄 РеСтарт", callback_data="restart_bot")
    builder.button(text="🟢 Старт", callback_data="start")
    builder.button(text="🔴 Стоп", callback_data="stop")
    builder.button(text="💬 Чаты", callback_data="info:chat")
    builder.button(
        text="🗂 Получить Папки",
        callback_data="processed_users",
    )
    builder.button(text="<-", callback_data=f"back:{back_to}")
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup()


async def ik_cancel_action(back_to: str = "default") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Отмена", callback_data=f"cancel:{back_to}")],
        ]
    )


async def ik_add_or_delete(
    current_page: int,
    all_page: int,
    back_to: str = "default",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    adjust = []
    if all_page:
        builder.button(
            text=f"{current_page} / {all_page}", callback_data="info_about_pages"
        )
        adjust.append(1)
    if all_page > 1:
        builder.button(text="<--", callback_data="arrow_left")
        builder.button(text="-->", callback_data="arrow_right")
        adjust.append(2)
    builder.button(text="➕ Добавить", callback_data="add")
    builder.button(text="➖ Удалить", callback_data="del")
    builder.button(text="<-", callback_data=f"back:{back_to}")
    builder.adjust(*adjust, 1, 1, 1)
    return builder.as_markup()


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


async def ik_processed_users(
    all_page: int,
    current_page: int,
    choices: list[bool],
    back_to: str = "default",
):
    builder = InlineKeyboardBuilder()
    adjust = []
    if all_page:
        builder.button(
            text=f"{current_page} / {all_page}", callback_data="info_about_pages"
        )
        adjust.append(1)
    if all_page > 1:
        builder.button(text="<--", callback_data="u:arrow_left")
        builder.button(text="-->", callback_data="u:arrow_right")
        adjust.append(2)
    n, u, c = choices
    builder.button(text=f"n {'🔘' if n else ''}", callback_data="f_first_name")
    builder.button(text=f"u {'🔘' if u else ''}", callback_data="f_username")
    builder.button(text=f"c {'🔘' if c else ''}", callback_data="f_copy")
    builder.button(text="<-", callback_data=f"back:{back_to}")
    builder.adjust(*adjust, 3, 1)
    return builder.as_markup()


async def ik_history_back(all_page: int, current_page: int, back_to: str = "default"):
    builder = InlineKeyboardBuilder()
    adjust = []
    if all_page:
        builder.button(
            text=f"{current_page} / {all_page}", callback_data="info_about_pages"
        )
        adjust.append(1)
    if all_page > 1:
        builder.button(text="<--", callback_data="h:arrow_left")
        builder.button(text="-->", callback_data="h:arrow_right")
        adjust.append(2)
    builder.button(text="<-", callback_data=f"back:{back_to}")
    builder.adjust(*adjust, 1)
    return builder.as_markup()


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


async def ik_folders(folders_name: list[str], back_to: str = "default"):
    builder = InlineKeyboardBuilder()
    for folder_name in folders_name:
        builder.button(text=folder_name, callback_data=f"folder:{folder_name}")
    builder.button(text="<-", callback_data=f"back:{back_to}")
    builder.adjust(2)
    return builder.as_markup()
