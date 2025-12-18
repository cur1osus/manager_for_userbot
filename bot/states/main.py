from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    enter_api_id = State()
    enter_api_hash = State()
    enter_phone = State()
    enter_code = State()
    enter_password = State()
    action = State()

    send_files = State()
    send_files_do = State()


class InfoState(StatesGroup):
    info = State()
    chats_info = State()
    add = State()
    chats_add = State()
    delete = State()
    chats_delete = State()


class BotState(StatesGroup):
    main = State()
    folders = State()


class BotFolderState(StatesGroup):
    enter_name = State()
