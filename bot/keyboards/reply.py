import logging

from aiogram.utils.keyboard import ReplyKeyboardBuilder

logger = logging.getLogger(__name__)

BTN_START = "🚀 Старт"
BTN_FILES = "📂 Файлы"
BTN_CLEAR = "🧹 Очистить"
BTN_CANCEL = "Отмена"


async def rk_cancel():
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_CANCEL)
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


async def rk_processing(mode_label: str | None = None):
    """Клавиатура для процессов с файлами: старт, список, очистка, отмена."""

    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_START)
    builder.button(text=BTN_FILES)
    builder.button(text=BTN_CLEAR)

    if mode_label:
        builder.button(text=mode_label)

    builder.button(text=BTN_CANCEL)

    if mode_label:
        builder.adjust(2, 2, 1)
    else:
        builder.adjust(2, 1, 1)

    return builder.as_markup(resize_keyboard=True)
