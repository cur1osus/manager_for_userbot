import logging
from typing import Final

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.models import Bot, BotFolder, UserManager

from .factories import (
    ArrowFoldersFactory,
    ArrowHistoryFactory,
    ArrowInfoFactory,
    BackFactory,
    BotAddFactory,
    BotFactory,
    BotFolderDeleteFactory,
    BotFolderFactory,
    BotMoveToFolderFactory,
    CancelFactory,
    DeleteInfoFactory,
    FolderFactory,
    FolderGetFactory,
    FormattingFactory,
    InfoFactory,
    UserPerMinuteFactory,
)

logger = logging.getLogger(__name__)

_CONFIRM_YES = "clear_analyzed_yes"
_CONFIRM_NO = "clear_analyzed_no"


async def ik_main_menu(user: UserManager) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"👥 Все боты [{len(user.bots)}]", callback_data="bots_all")
    builder.button(text=f"📂 Все папки [{len(user.folders)}]", callback_data="bots")
    # builder.button(text="❇️ Добавить бота", callback_data="add_new_bot")
    builder.button(text="ИТОИ", callback_data="itoi")
    builder.button(text="🚷 Баны", callback_data=InfoFactory(key="ban"))
    builder.button(
        text=f"🤖 Антифлуд: {'🟢' if user.is_antiflood_mode else '🔴'}",
        callback_data="antiflood_mode",
    )
    builder.button(
        text=f"🏃🏼‍➡️ Пропускная: {user.users_per_minute}",
        callback_data="users_per_minute",
    )
    builder.adjust(2, 2, 2)
    return builder.as_markup()


async def ik_itoi_menu(user: UserManager) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"❌ Игноры [{len(user.ignored_words)}]",
        callback_data=InfoFactory(key="ignore"),
    )
    builder.button(
        text=f"❗️ Тригеры [{len(user.keywords)}]",
        callback_data=InfoFactory(key="keyword"),
    )
    builder.button(
        text=f"🗣 Ответы [{len(user.messages_to_answer)}]",
        callback_data=InfoFactory(key="answer"),
    )
    builder.button(
        text="🔍 История",
        callback_data="history",
    )
    builder.button(text="<-", callback_data=BackFactory(to="default"))
    builder.adjust(2, 2, 1)
    return builder.as_markup()


async def ik_available_bots(
    bots_data: list[Bot],
    back_to: str = "default",
    delete_folder_id: int | None = None,
    add_to_folder_id: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if add_to_folder_id is not None:
        builder.button(
            text="➕ Добавить аккаунт",
            callback_data=BotAddFactory(folder_id=add_to_folder_id),
        )
    if delete_folder_id is not None:
        builder.button(
            text="🗑 Удалить папку",
            callback_data=BotFolderDeleteFactory(id=delete_folder_id),
        )
    if bots_data:
        for bot in bots_data:
            builder.button(
                text=f"{'❇️' if bot.is_connected else '⛔️'} {'🟢' if bot.is_started else '🔴'} {bot.phone} ({bot.name or '🌀'}) [{bot.id}]",
                callback_data=BotFactory(id=bot.id),
            )
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_bot_folder_list(
    folders: list[BotFolder],
    back_to: str = "default",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать папку", callback_data="bots_create_folder")
    # builder.button(text="📂 Без папки", callback_data="bots_no_folder")
    for folder in folders:
        builder.button(
            text=f"📁 {folder.name}",
            callback_data=BotFolderFactory(id=folder.id),
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
    builder.button(text="📂 Переместить", callback_data="move_bot_folder")
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(1, 2, 2, 1, 1)
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
    builder.button(text="📂 Переместить в папку", callback_data="move_bot_folder")
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


async def ik_move_bot_folders(
    folders: list[BotFolder],
    current_folder_id: int | None,
    back_to: str = "bot_actions",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    no_folder_checked = current_folder_id is None
    builder.button(
        text=f"Без папки{' 🔘' if no_folder_checked else ''}",
        callback_data=BotMoveToFolderFactory(id=0),
    )
    for folder in folders:
        is_current = folder.id == current_folder_id
        builder.button(
            text=f"{folder.name}{' 🔘' if is_current else ''}",
            callback_data=BotMoveToFolderFactory(id=folder.id),
        )
    builder.button(text="<-", callback_data=BackFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_tool_for_not_accepted_message() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚷", callback_data="ban_user")
    builder.button(text="🚮", callback_data="in_the_trash")
    builder.button(text="✍🏻", callback_data="send_message")
    builder.button(text="👁", callback_data="view_full_message")
    builder.adjust(2, 2)
    return builder.as_markup()


async def ik_tool_for_pack_users() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍🏻", callback_data="send_messages")
    builder.adjust(1)
    return builder.as_markup()


async def ik_confirm_clear_keyboard(
    yes_callback: str = _CONFIRM_YES,
    no_callback: str = _CONFIRM_NO,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, удалить", callback_data=yes_callback)
    builder.button(text="Нет, отмена", callback_data=no_callback)
    builder.adjust(2)
    return builder.as_markup()
