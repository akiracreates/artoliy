import asyncio
import logging
import sys
from urllib.parse import quote

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.api import BackendAPI
from app.config import settings
from app.keyboards import main_menu
from app.states import (
    CreateProfileStates,
    EditProfileStates,
    AdminActivateStates,
    AdminDeleteUserStates,
)
from app.utils import format_profile, parse_tags


dp = Dispatcher()
api = BackendAPI()


async def safe_is_admin(user_id: int) -> bool:
    try:
        data = await api.get(f"/debug/admin-check/{user_id}")
        return bool(data.get("is_admin", False))
    except Exception:
        logging.exception("Failed to check admin status for user_id=%s", user_id)
        return False

@dp.message(CommandStart())
async def start_handler(message: Message):
    is_admin = await safe_is_admin(message.from_user.id)

    text = (
        "Welcome to <b>Artoliy</b>.\n"
        "This bot lets artists create a portfolio-style profile and lets users browse artists by tag.\n\n"
        "Available actions:\n"
        "• Create profile\n"
        "• My profile\n"
        "• Edit profile\n"
        "• Delete profile\n"
        "• Browse tags\n"
        "• Browse by tag\n"
        "• Activate admin"
    )

    if is_admin:
        text += "\n• Admin list users\n• Admin delete user\n• Admin flush redis"

    await message.answer(text, reply_markup=main_menu(is_admin=is_admin))


@dp.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("There is nothing to cancel.")
        return

    await state.clear()
    is_admin = await safe_is_admin(message.from_user.id)
    await message.answer("Action cancelled.", reply_markup=main_menu(is_admin=is_admin))


@dp.message(F.text == "Create profile")
@dp.message(Command("create"))
async def create_profile_start(message: Message, state: FSMContext):
    try:
        exists = await api.get(f"/users/{message.from_user.id}/exists")
        if exists["exists"]:
            await message.answer("You already have a profile. Use 'Edit profile' instead.")
            return
    except Exception:
        await message.answer("Could not check your profile right now.")
        return

    await state.set_state(CreateProfileStates.display_name)
    await message.answer("Enter your display name:")


@dp.message(CreateProfileStates.display_name)
async def create_profile_display_name(message: Message, state: FSMContext):
    await state.update_data(display_name=message.text.strip())
    await state.set_state(CreateProfileStates.artist_name)
    await message.answer("Enter your artist name:")


@dp.message(CreateProfileStates.artist_name)
async def create_profile_artist_name(message: Message, state: FSMContext):
    await state.update_data(artist_name=message.text.strip())
    await state.set_state(CreateProfileStates.short_bio)
    await message.answer("Enter a short bio, or type '-' to skip:")


@dp.message(CreateProfileStates.short_bio)
async def create_profile_short_bio(message: Message, state: FSMContext):
    value = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(short_bio=value)
    await state.set_state(CreateProfileStates.portfolio_link)
    await message.answer("Enter your portfolio link, or type '-' to skip:")


@dp.message(CreateProfileStates.portfolio_link)
async def create_profile_portfolio_link(message: Message, state: FSMContext):
    value = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(portfolio_link=value)
    await state.set_state(CreateProfileStates.contact_info)
    await message.answer("Enter contact info, or type '-' to skip:")


@dp.message(CreateProfileStates.contact_info)
async def create_profile_contact_info(message: Message, state: FSMContext):
    value = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(contact_info=value)
    await state.set_state(CreateProfileStates.commission_status)
    await message.answer("Enter commission status: open or closed")


@dp.message(CreateProfileStates.commission_status)
async def create_profile_commission_status(message: Message, state: FSMContext):
    status = message.text.strip().lower()
    if status not in {"open", "closed"}:
        await message.answer("Please enter only: open or closed")
        return

    await state.update_data(commission_status=status)
    await state.set_state(CreateProfileStates.tags)
    await message.answer("Enter tags separated by commas, or type '-' to skip:")


@dp.message(CreateProfileStates.tags)
async def create_profile_tags(message: Message, state: FSMContext):
    tags = [] if message.text.strip() == "-" else parse_tags(message.text)
    await state.update_data(tags=tags)
    await state.set_state(CreateProfileStates.price_range)
    await message.answer("Enter your price range, or type '-' to skip:")


@dp.message(CreateProfileStates.price_range)
async def create_profile_price_range(message: Message, state: FSMContext):
    price_range = None if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()

    payload = {
        "telegram_user_id": message.from_user.id,
        "display_name": data["display_name"],
        "artist_name": data["artist_name"],
        "username": message.from_user.username,
        "short_bio": data.get("short_bio"),
        "portfolio_link": data.get("portfolio_link"),
        "contact_info": data.get("contact_info"),
        "commission_status": data["commission_status"],
        "tags": data.get("tags", []),
        "price_range": price_range,
    }

    try:
        profile = await api.post("/users", json=payload)
        await message.answer("Profile created successfully.")
        await message.answer(format_profile(profile))
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Backend error.")
        await message.answer(f"Could not create profile: {detail}")
    except Exception:
        await message.answer("Unexpected error while creating profile.")
    finally:
        await state.clear()


@dp.message(F.text == "My profile")
@dp.message(Command("me"))
async def my_profile_handler(message: Message):
    try:
        profile = await api.get(
            f"/users/{message.from_user.id}",
            params={"actor_telegram_user_id": message.from_user.id},
        )
        await message.answer(format_profile(profile))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await message.answer("You do not have a profile yet.")
        else:
            detail = e.response.json().get("detail", "Backend error.")
            await message.answer(f"Could not load profile: {detail}")
    except Exception:
        await message.answer("Unexpected error while loading your profile.")


@dp.message(F.text == "Edit profile")
@dp.message(Command("edit"))
async def edit_profile_start(message: Message, state: FSMContext):
    try:
        exists = await api.get(f"/users/{message.from_user.id}/exists")
        if not exists["exists"]:
            await message.answer("You do not have a profile yet. Use 'Create profile' first.")
            return
    except Exception:
        logging.exception("Failed to check profile before edit for user_id=%s", message.from_user.id)
        await message.answer("Could not check your profile right now.")
        return

    await state.set_state(EditProfileStates.field)
    await message.answer(
        "Which field do you want to edit?\n"
        "Available fields:\n"
        "display_name\nartist_name\nshort_bio\nportfolio_link\ncontact_info\ncommission_status\ntags\nprice_range"
    )

@dp.message(EditProfileStates.field)
async def edit_profile_field(message: Message, state: FSMContext):
    allowed = {
        "display_name",
        "artist_name",
        "short_bio",
        "portfolio_link",
        "contact_info",
        "commission_status",
        "tags",
        "price_range",
    }

    field = message.text.strip()
    if field not in allowed:
        await message.answer("Unknown field. Please enter one of the listed field names.")
        return

    await state.update_data(field=field)
    await state.set_state(EditProfileStates.value)
    await message.answer("Enter the new value. Type '-' to clear optional text fields.")


@dp.message(EditProfileStates.value)
async def edit_profile_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["field"]
    raw_value = message.text.strip()

    if field == "commission_status":
        value = raw_value.lower()
        if value not in {"open", "closed"}:
            await message.answer("Please enter only: open or closed")
            return
    elif field == "tags":
        value = [] if raw_value == "-" else parse_tags(raw_value)
    else:
        value = None if raw_value == "-" else raw_value

    try:
        profile = await api.patch(
            f"/users/{message.from_user.id}",
            json={field: value},
            params={"actor_telegram_user_id": message.from_user.id},
        )
        await message.answer("Profile updated successfully.")
        await message.answer(format_profile(profile))
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Backend error.")
        await message.answer(f"Could not update profile: {detail}")
    except Exception:
        await message.answer("Unexpected error while updating profile.")
    finally:
        await state.clear()


@dp.message(F.text == "Delete profile")
@dp.message(Command("delete"))
async def delete_profile_handler(message: Message):
    try:
        result = await api.delete(
            f"/users/{message.from_user.id}",
            params={"actor_telegram_user_id": message.from_user.id},
        )
        await message.answer(result.get("message", "Profile deleted."))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await message.answer("You do not have a profile to delete.")
        else:
            detail = e.response.json().get("detail", "Backend error.")
            await message.answer(f"Could not delete profile: {detail}")
    except Exception:
        await message.answer("Unexpected error while deleting profile.")


@dp.message(F.text == "Browse tags")
@dp.message(Command("tags"))
async def browse_tags_handler(message: Message):
    try:
        data = await api.get("/artists/tags")
        tags = data.get("tags", [])
        if not tags:
            await message.answer("No tags available yet.")
            return
        await message.answer("Available tags:\n" + "\n".join(f"• {tag}" for tag in tags))
    except Exception:
        await message.answer("Could not load tags right now.")


@dp.message(F.text == "Browse by tag")
async def browse_by_tag_help_handler(message: Message):
    await message.answer("Send: /tag portraits\nExample: /tag anime")


@dp.message(Command("tag"))
async def browse_by_tag_handler(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /tag portraits")
        return

    tag = parts[1].strip()

    try:
        encoded_tag = quote(tag, safe="")
        data = await api.get(f"/artists/by-tag/{encoded_tag}")
        profiles = data.get("profiles", [])
        total = data.get("total", 0)

        if total == 0:
            await message.answer(f"No artists found for tag: {tag}")
            return

        await message.answer(f"Found {total} artist(s) for tag: {data.get('tag')}")
        for profile in profiles:
            await message.answer(format_profile(profile))
    except Exception:
        await message.answer("Could not browse artists by tag right now.")


@dp.message(F.text == "Activate admin")
@dp.message(Command("admin"))
async def activate_admin_start(message: Message, state: FSMContext):
    await state.set_state(AdminActivateStates.code)
    await message.answer("Enter the admin code:")


@dp.message(AdminActivateStates.code)
async def activate_admin_code(message: Message, state: FSMContext):
    try:
        result = await api.post(
            "/admin/activate",
            json={
                "telegram_user_id": message.from_user.id,
                "admin_code": message.text.strip(),
            },
        )
        await message.answer(result.get("message", "Admin activated."))
        await message.answer(result.get("message", "Admin activated."))
        await message.answer(
            "Admin menu is now available.",
            reply_markup=main_menu(is_admin=True),
        )
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Backend error.")
        await message.answer(f"Could not activate admin: {detail}")
    except Exception:
        await message.answer("Unexpected error while activating admin.")
    finally:
        await state.clear()

@dp.message(F.text == "Admin delete user")
@dp.message(Command("admin_delete"))
async def admin_delete_user_start(message: Message, state: FSMContext):
    is_admin = await safe_is_admin(message.from_user.id)
    if not is_admin:
        await message.answer("Admin access required.")
        return

    await state.set_state(AdminDeleteUserStates.target_user_id)
    await message.answer("Enter the Telegram user ID of the profile you want to delete:")


@dp.message(AdminDeleteUserStates.target_user_id)
async def admin_delete_user_finish(message: Message, state: FSMContext):
    is_admin = await safe_is_admin(message.from_user.id)
    if not is_admin:
        await state.clear()
        await message.answer("Admin access required.")
        return

    raw_value = message.text.strip()

    if not raw_value.isdigit():
        await message.answer("User ID must be a number.")
        return

    target_user_id = int(raw_value)

    try:
        result = await api.delete(
            f"/admin/users/{target_user_id}",
            params={"actor_telegram_user_id": message.from_user.id},
        )
        await message.answer(result.get("message", "Profile deleted successfully by admin."))
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await message.answer("Profile not found.")
        else:
            detail = e.response.json().get("detail", "Backend error.")
            await message.answer(f"Could not delete user: {detail}")
    except Exception:
        logging.exception("Unexpected error while deleting user as admin")
        await message.answer("Unexpected error while deleting user.")
    finally:
        await state.clear()



@dp.message(F.text == "Admin list users")
@dp.message(Command("admin_list"))
async def admin_list_users_handler(message: Message):
    try:
        users = await api.get("/admin/users", params={"actor_telegram_user_id": message.from_user.id})
        if not users:
            await message.answer("No profiles found.")
            return

        await message.answer(f"Total profiles: {len(users)}")
        for profile in users:
            await message.answer(format_profile(profile))
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Backend error.")
        await message.answer(f"Could not list users: {detail}")
    except Exception:
        await message.answer("Unexpected error while listing users.")


@dp.message(F.text == "Admin flush redis")
@dp.message(Command("admin_flush"))
async def admin_flush_handler(message: Message):
    try:
        result = await api.delete(
            "/admin/redis/flush",
            params={"actor_telegram_user_id": message.from_user.id},
        )
        await message.answer(result.get("message", "Redis project data cleared."))
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", "Backend error.")
        await message.answer(f"Could not flush Redis: {detail}")
    except Exception:
        await message.answer("Unexpected error while flushing Redis.")


@dp.message()
async def fallback_handler(message: Message):
    await message.answer("Unknown command. Use /start to open the menu.")


async def main() -> None:
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing in bot/.env")

    await api.startup()
    try:
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        await dp.start_polling(bot)
    finally:
        await api.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())