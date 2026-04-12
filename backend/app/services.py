from contextlib import contextmanager
from datetime import datetime, UTC
import time
import uuid

from app.config import settings
from app.dependencies import redis_client
from app.redis_keys import (
    ADMINS_KEY,
    PROJECT_FLUSH_LOCK_KEY,
    USERS_ALL_KEY,
    tag_index_key,
    user_lock_key,
    user_profile_key,
    user_tags_key,
)
from app.schemas import ProfileCreate, ProfileResponse, ProfileUpdate


PROFILE_HASH_FIELDS = {
    "telegram_user_id",
    "display_name",
    "artist_name",
    "username",
    "short_bio",
    "portfolio_link",
    "contact_info",
    "commission_status",
    "price_range",
    "created_at",
    "updated_at",
}

TEXT_FIELDS = {
    "display_name",
    "artist_name",
    "username",
    "short_bio",
    "portfolio_link",
    "contact_info",
    "price_range",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def normalize_tag(tag: str) -> str:
    return " ".join(tag.strip().lower().split())


def normalize_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        normalized = normalize_tag(tag)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)

    return cleaned


@contextmanager
def redis_lock(lock_key: str, timeout_seconds: int = 5, wait_seconds: float = 3.0):
    token = str(uuid.uuid4())
    deadline = time.monotonic() + wait_seconds

    while time.monotonic() < deadline:
        acquired = redis_client.set(lock_key, token, nx=True, ex=timeout_seconds)
        if acquired:
            try:
                yield
                return
            finally:
                current = redis_client.get(lock_key)
                if current == token:
                    redis_client.delete(lock_key)
        time.sleep(0.05)

    raise TimeoutError(f"Could not acquire lock: {lock_key}")


def user_exists(telegram_user_id: int) -> bool:
    return redis_client.exists(user_profile_key(telegram_user_id)) == 1


def is_admin(telegram_user_id: int) -> bool:
    if telegram_user_id in settings.admin_ids:
        return True
    return bool(redis_client.sismember(ADMINS_KEY, str(telegram_user_id)))


def can_manage_profile(actor_telegram_user_id: int, target_telegram_user_id: int) -> bool:
    return actor_telegram_user_id == target_telegram_user_id or is_admin(actor_telegram_user_id)


def activate_admin(telegram_user_id: int, admin_code: str) -> bool:
    if not settings.ADMIN_CODE:
        return False

    if admin_code != settings.ADMIN_CODE:
        return False

    redis_client.sadd(ADMINS_KEY, telegram_user_id)
    return True


def build_profile_hash_payload(profile: ProfileCreate, created_at: str, updated_at: str) -> dict[str, str]:
    display_name = normalize_text(profile.display_name)
    artist_name = normalize_text(profile.artist_name)

    if not display_name or not artist_name:
        raise ValueError("display_name and artist_name must not be empty.")

    return {
        "telegram_user_id": str(profile.telegram_user_id),
        "display_name": display_name,
        "artist_name": artist_name,
        "username": normalize_text(profile.username) or "",
        "short_bio": normalize_text(profile.short_bio) or "",
        "portfolio_link": normalize_text(profile.portfolio_link) or "",
        "contact_info": normalize_text(profile.contact_info) or "",
        "commission_status": profile.commission_status,
        "price_range": normalize_text(profile.price_range) or "",
        "created_at": created_at,
        "updated_at": updated_at,
    }


def set_user_tags_atomic(pipe, telegram_user_id: int, old_tags: set[str], new_tags: list[str]) -> None:
    for old_tag in old_tags:
        pipe.srem(tag_index_key(old_tag), telegram_user_id)

    pipe.delete(user_tags_key(telegram_user_id))

    if new_tags:
        pipe.sadd(user_tags_key(telegram_user_id), *new_tags)
        for tag in new_tags:
            pipe.sadd(tag_index_key(tag), telegram_user_id)


def create_user_profile(profile: ProfileCreate) -> ProfileResponse:
    lock_key = user_lock_key(profile.telegram_user_id)

    with redis_lock(lock_key):
        if user_exists(profile.telegram_user_id):
            raise ValueError("Profile already exists for this Telegram user.")

        created_at = now_iso()
        updated_at = created_at

        payload = build_profile_hash_payload(profile, created_at=created_at, updated_at=updated_at)
        normalized_tags = normalize_tags(profile.tags)

        pipe = redis_client.pipeline()
        pipe.hset(user_profile_key(profile.telegram_user_id), mapping=payload)
        pipe.sadd(USERS_ALL_KEY, profile.telegram_user_id)
        set_user_tags_atomic(pipe, profile.telegram_user_id, set(), normalized_tags)
        pipe.execute()

    created_profile = get_user_profile(profile.telegram_user_id)
    if created_profile is None:
        raise RuntimeError("Profile was created but could not be read back from Redis.")
    return created_profile


def get_user_profile(telegram_user_id: int) -> ProfileResponse | None:
    profile_data = redis_client.hgetall(user_profile_key(telegram_user_id))
    if not profile_data:
        return None

    tags = sorted(redis_client.smembers(user_tags_key(telegram_user_id)))

    return ProfileResponse(
        telegram_user_id=int(profile_data["telegram_user_id"]),
        display_name=profile_data["display_name"],
        artist_name=profile_data["artist_name"],
        username=profile_data["username"] or None,
        short_bio=profile_data["short_bio"] or None,
        portfolio_link=profile_data["portfolio_link"] or None,
        contact_info=profile_data["contact_info"] or None,
        commission_status=profile_data["commission_status"],
        tags=tags,
        price_range=profile_data["price_range"] or None,
        created_at=profile_data["created_at"],
        updated_at=profile_data["updated_at"],
    )


def update_user_profile(telegram_user_id: int, profile_update: ProfileUpdate) -> ProfileResponse | None:
    lock_key = user_lock_key(telegram_user_id)

    with redis_lock(lock_key):
        existing = redis_client.hgetall(user_profile_key(telegram_user_id))
        if not existing:
            return None

        old_tags = redis_client.smembers(user_tags_key(telegram_user_id))
        update_data = profile_update.model_dump(exclude_unset=True)
        tags = update_data.pop("tags", None)

        hash_updates: dict[str, str] = {}

        for key, value in update_data.items():
            if key not in PROFILE_HASH_FIELDS:
                continue

            if key in TEXT_FIELDS:
                value = normalize_text(value)

            if key in {"display_name", "artist_name"} and not value:
                raise ValueError(f"{key} must not be empty.")

            hash_updates[key] = value if value is not None else ""

        hash_updates["updated_at"] = now_iso()

        pipe = redis_client.pipeline()

        if hash_updates:
            pipe.hset(user_profile_key(telegram_user_id), mapping=hash_updates)

        if tags is not None:
            normalized_tags = normalize_tags(tags)
            set_user_tags_atomic(pipe, telegram_user_id, old_tags, normalized_tags)

        pipe.execute()

    return get_user_profile(telegram_user_id)


def delete_user_profile(telegram_user_id: int) -> bool:
    lock_key = user_lock_key(telegram_user_id)

    with redis_lock(lock_key):
        if not user_exists(telegram_user_id):
            return False

        tags = redis_client.smembers(user_tags_key(telegram_user_id))

        pipe = redis_client.pipeline()
        pipe.delete(user_profile_key(telegram_user_id))
        pipe.delete(user_tags_key(telegram_user_id))
        pipe.delete(user_lock_key(telegram_user_id))
        pipe.srem(USERS_ALL_KEY, telegram_user_id)

        for tag in tags:
            pipe.srem(tag_index_key(tag), telegram_user_id)

        pipe.execute()

    return True


def list_all_user_ids() -> list[int]:
    raw_ids = redis_client.smembers(USERS_ALL_KEY)
    return sorted(int(user_id) for user_id in raw_ids)


def list_all_profiles() -> list[ProfileResponse]:
    profiles: list[ProfileResponse] = []
    for user_id in list_all_user_ids():
        profile = get_user_profile(user_id)
        if profile is not None:
            profiles.append(profile)
    return profiles


def list_all_tags() -> list[str]:
    all_tags: set[str] = set()

    for user_id in list_all_user_ids():
        tags = redis_client.smembers(user_tags_key(user_id))
        for tag in tags:
            normalized = normalize_tag(tag)
            if normalized:
                all_tags.add(normalized)

    return sorted(all_tags)


def get_profiles_by_tag(tag: str) -> list[ProfileResponse]:
    normalized = normalize_tag(tag)
    if not normalized:
        return []

    user_ids = redis_client.smembers(tag_index_key(normalized))
    profiles: list[ProfileResponse] = []

    for user_id in sorted(user_ids, key=int):
        profile = get_user_profile(int(user_id))
        if profile is not None:
            profiles.append(profile)

    return profiles


def flush_all_project_data() -> None:
    with redis_lock(PROJECT_FLUSH_LOCK_KEY, timeout_seconds=10, wait_seconds=5):
        user_ids = list_all_user_ids()
        pipe = redis_client.pipeline()

        for user_id in user_ids:
            tags = redis_client.smembers(user_tags_key(user_id))

            pipe.delete(user_profile_key(user_id))
            pipe.delete(user_tags_key(user_id))
            pipe.delete(user_lock_key(user_id))

            for tag in tags:
                pipe.delete(tag_index_key(tag))

        pipe.delete(USERS_ALL_KEY)
        pipe.delete(ADMINS_KEY)
        pipe.execute()