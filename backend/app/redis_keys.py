def user_profile_key(telegram_user_id: int) -> str:
    return f"user:{telegram_user_id}"


def user_tags_key(telegram_user_id: int) -> str:
    return f"user:{telegram_user_id}:tags"


def tag_index_key(tag: str) -> str:
    return f"tag:{tag}"


def user_lock_key(telegram_user_id: int) -> str:
    return f"lock:user:{telegram_user_id}"


USERS_ALL_KEY = "users:all"
ADMINS_KEY = "admins"
PROJECT_FLUSH_LOCK_KEY = "lock:project:flush"