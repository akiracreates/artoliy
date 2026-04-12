from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="Create profile"), KeyboardButton(text="My profile")],
        [KeyboardButton(text="Edit profile"), KeyboardButton(text="Delete profile")],
        [KeyboardButton(text="Browse tags"), KeyboardButton(text="Browse by tag")],
    ]

    if is_admin:
        rows.append([KeyboardButton(text="Admin list users"), KeyboardButton(text="Admin delete user")])
        rows.append([KeyboardButton(text="Admin flush redis")])

    rows.append([KeyboardButton(text="Activate admin")])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Choose an action",
    )