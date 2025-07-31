from aiogram.filters.callback_data import CallbackData


class InfoFactory(CallbackData, prefix="i"):
    key: str


class ArrowInfoFactory(CallbackData, prefix="ai"):
    to: str


class ArrowHistoryFactory(CallbackData, prefix="ah"):
    to: str


class ArrowFoldersFactory(CallbackData, prefix="af"):
    to: str


class DeleteInfoFactory(CallbackData, prefix="di"):
    id: int


class BotFactory(CallbackData, prefix="b"):
    id: int


class FolderFactory(CallbackData, prefix="f"):
    name: str


class FolderGetFactory(CallbackData, prefix="fg"):
    name: str


class FormattingFactory(CallbackData, prefix="fm"):
    format: str


class BackFactory(CallbackData, prefix="bk"):
    to: str


class CancelFactory(CallbackData, prefix="cn"):
    to: str


class UserPerMinuteFactory(CallbackData, prefix="upm"):
    value: int
