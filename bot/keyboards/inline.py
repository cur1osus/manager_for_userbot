import logging
from typing import Final

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.mysql.models import Bot

from .factories import (
    ArrowFoldersFactory,
    ArrowHistoryFactory,
    ArrowInfoFactory,
    BackFactory,
    BotFactory,
    CancelFactory,
    DeleteInfoFactory,
    FolderFactory,
    FolderGetFactory,
    FormattingFactory,
    InfoFactory,
    UserPerMinuteFactory,
)

logger = logging.getLogger(__name__)


async def ik_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Боты", callback_data="bots")
    builder.button(text="❇️ Добавить бота", callback_data="add_new_bot")
    builder.button(text="❌ Игноры", callback_data=InfoFactory(key="ignore"))
    builder.button(text="🚷 Баны", callback_data=InfoFactory(key="ban"))
    builder.button(text="❗️Тригеры", callback_data=InfoFactory(key="keyword"))
    builder.button(text="🗣 Ответы", callback_data=InfoFactory(key="answer"))
    builder.button(
        text="🏃🏼‍➡️ Пропускная способность",
        callback_data="users_per_minute",
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
                text=f"{'❇️' if bot.is_connected else '⛔️'} {'🟢' if bot.is_started else '🔴'} {bot.phone} ({bot.name or '🌀'}) [{bot.id}]",
                callback_data=BotFactory(id=bot.id),
            )
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_action_with_bot(back_to: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⛓️‍💥 Отключить", callback_data="disconnected")
    builder.button(text="🟢 Старт", callback_data="start")
    builder.button(text="🔴 Стоп", callback_data="stop")
    builder.button(text="💬 Чаты", callback_data=InfoFactory(key="chats"))
    builder.button(
        text="🗂 Получить Папки",
        callback_data="processed_users",
    )
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup()


async def ik_cancel_action(back_to: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data=CancelFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


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
        builder.button(
            text="<--",
            callback_data=ArrowInfoFactory(to="left"),
        )
        builder.button(
            text="-->",
            callback_data=ArrowInfoFactory(to="right"),
        )
        adjust.append(2)
    builder.button(text="➕ Добавить", callback_data="add")
    builder.button(text="➖ Удалить", callback_data="delete")
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(*adjust, 1, 1, 1)
    return builder.as_markup()


limit_button: Final = 80


async def ik_num_matrix_del(
    ids: list[int], back_to: str = "default"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = 0
    if len(ids) > limit_button:
        start = len(ids) - limit_button
        ids = ids[start:]
    for ind, id in enumerate(ids, start):
        builder.button(text=str(ind + 1), callback_data=DeleteInfoFactory(id=id))
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(5)
    return builder.as_markup()


max_users_per_minute: Final = 30


async def ik_num_matrix_users(
    current_choose: int, back_to: str = "default"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, max_users_per_minute + 1):
        if current_choose == i:
            builder.button(text=f"{i}🔘", callback_data=UserPerMinuteFactory(value=i))
            continue
        builder.button(text=str(i), callback_data=UserPerMinuteFactory(value=i))
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(5)
    return builder.as_markup()


async def ik_processed_users(
    all_page: int,
    current_page: int,
    choices: list[bool],
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
        builder.button(text="<--", callback_data=ArrowFoldersFactory(to="left"))
        builder.button(text="-->", callback_data=ArrowFoldersFactory(to="right"))
        adjust.append(2)
    n, u, c = choices
    builder.button(
        text=f"n{'🔘' if n else ''}",
        callback_data=FormattingFactory(format="n"),
    )
    builder.button(
        text=f"u{'🔘' if u else ''}",
        callback_data=FormattingFactory(format="u"),
    )
    builder.button(
        text=f"c{'🔘' if c else ''}",
        callback_data=FormattingFactory(format="c"),
    )
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(*adjust, 3, 1)
    return builder.as_markup()


async def ik_history_back(
    all_page: int, current_page: int, back_to: str = "default"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    adjust = []
    if all_page:
        builder.button(
            text=f"{current_page} / {all_page}", callback_data="info_about_pages"
        )
        adjust.append(1)
    if all_page > 1:
        builder.button(text="<--", callback_data=ArrowHistoryFactory(to="left"))
        builder.button(text="-->", callback_data=ArrowHistoryFactory(to="right"))
        adjust.append(2)
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(*adjust, 1)
    return builder.as_markup()


async def ik_back(back_to: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_connect_bot(back_to: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить", callback_data="delete")
    builder.button(text="❇️ Подключить", callback_data="connect")
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_folders(
    folders: dict[str, bool], back_to: str = "default"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if folders:
        for folder_name, is_chosen in folders.items():
            builder.button(
                text=f"{folder_name}{'🔘' if is_chosen else ''}",
                callback_data=FolderFactory(name=folder_name),
            )
        builder.button(text="✔️ Подтвердить выбор", callback_data="accept_folders")
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(2)
    return builder.as_markup()


async def ik_folders_with_users(
    folders: list[str], back_to: str = "default"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if folders:
        for folder_name in folders:
            builder.button(
                text=f"{folder_name}", callback_data=FolderGetFactory(name=folder_name)
            )
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(2)
    return builder.as_markup()


async def ik_tool_for_not_accepted_message() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="test", callback_data="test")
    builder.adjust(1)
    return builder.as_markup()
