from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    enter_api_id = State()
    enter_api_hash = State()
    enter_phone = State()
    enter_code = State()
    enter_password = State()


