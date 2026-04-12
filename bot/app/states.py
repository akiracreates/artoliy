from aiogram.fsm.state import State, StatesGroup


class CreateProfileStates(StatesGroup):
    display_name = State()
    artist_name = State()
    short_bio = State()
    portfolio_link = State()
    contact_info = State()
    commission_status = State()
    tags = State()
    price_range = State()


class EditProfileStates(StatesGroup):
    field = State()
    value = State()


class AdminActivateStates(StatesGroup):
    code = State()


class AdminDeleteUserStates(StatesGroup):
    target_user_id = State()