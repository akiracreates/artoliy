from fastapi import FastAPI, HTTPException, Query

from app.config import settings
from app.dependencies import redis_client
from app.schemas import (
    AdminActivateRequest,
    AdminActivateResponse,
    ActorRequest,
    DeleteProfileRequest,
    ExistsResponse,
    MessageResponse,
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate,
    ProfilesByTagResponse,
    ProfilesExportResponse,
    TagListResponse,
)
from app.services import (
    activate_admin,
    can_manage_profile,
    create_user_profile,
    delete_user_profile,
    flush_all_project_data,
    get_profiles_by_tag,
    get_user_profile,
    is_admin,
    list_all_profiles,
    list_all_tags,
    list_all_user_ids,
    update_user_profile,
    user_exists,
    normalize_tag,
)


app = FastAPI(title=settings.APP_TITLE)


@app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@app.get("/redis-check")
async def redis_check():
    try:
        pong = redis_client.ping()
        return {
            "redis_connected": pong,
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
        }
    except Exception as e:
        return {
            "redis_connected": False,
            "error": str(e),
        }


@app.get("/config-check")
async def config_check():
    return {
        "redis_host": settings.REDIS_HOST,
        "redis_port": settings.REDIS_PORT,
        "admin_code_loaded": bool(settings.ADMIN_CODE),
        "admin_ids_count": len(settings.admin_ids),
    }


@app.get("/debug/admin-check/{telegram_user_id}")
async def admin_check(telegram_user_id: int):
    return {
        "telegram_user_id": telegram_user_id,
        "is_admin": is_admin(telegram_user_id),
    }


@app.get("/debug/users-count")
async def users_count():
    return {
        "count": len(list_all_user_ids())
    }


@app.get("/users/{telegram_user_id}/exists", response_model=ExistsResponse)
async def check_user_exists(telegram_user_id: int):
    return ExistsResponse(exists=user_exists(telegram_user_id))


@app.post("/users", response_model=ProfileResponse, status_code=201)
async def create_user(profile: ProfileCreate):
    try:
        return create_user_profile(profile)
    except ValueError as e:
        message = str(e)
        if "already exists" in message:
            raise HTTPException(status_code=409, detail=message)
        raise HTTPException(status_code=400, detail=message)
    except TimeoutError:
        raise HTTPException(status_code=409, detail="Another request for this profile is already in progress.")


@app.get("/users/{telegram_user_id}", response_model=ProfileResponse)
async def get_user(
    telegram_user_id: int,
    actor_telegram_user_id: int = Query(...),
):
    if not can_manage_profile(actor_telegram_user_id, telegram_user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to view this profile.")

    profile = get_user_profile(telegram_user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return profile


@app.patch("/users/{telegram_user_id}", response_model=ProfileResponse)
async def patch_user(
        telegram_user_id: int,
        profile_update: ProfileUpdate,
        actor_telegram_user_id: int = Query(...),
):
    if not can_manage_profile(actor_telegram_user_id, telegram_user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to update this profile.")

    try:
        updated_profile = update_user_profile(telegram_user_id, profile_update)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TimeoutError:
        raise HTTPException(status_code=409, detail="Another request for this profile is already in progress.")

    if updated_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return updated_profile


@app.delete("/users/{telegram_user_id}", response_model=MessageResponse)
async def delete_user(
    telegram_user_id: int,
    actor_telegram_user_id: int = Query(...),
):
    if not can_manage_profile(actor_telegram_user_id, telegram_user_id):
        raise HTTPException(status_code=403, detail="You do not have permission to delete this profile.")

    try:
        deleted = delete_user_profile(telegram_user_id)
    except TimeoutError:
        raise HTTPException(status_code=409, detail="Another request for this profile is already in progress.")

    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return MessageResponse(message="Profile deleted successfully.")


@app.post("/admin/activate", response_model=AdminActivateResponse)
async def admin_activate(payload: AdminActivateRequest):
    activated = activate_admin(payload.telegram_user_id, payload.admin_code)
    if not activated:
        raise HTTPException(status_code=403, detail="Invalid admin code.")

    return AdminActivateResponse(
        message="Admin rights activated successfully.",
        telegram_user_id=payload.telegram_user_id,
        is_admin=True,
    )


@app.get("/admin/users", response_model=list[ProfileResponse])
async def admin_list_users(actor_telegram_user_id: int = Query(...)):
    if not is_admin(actor_telegram_user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")

    return list_all_profiles()


@app.get("/admin/export/json", response_model=ProfilesExportResponse)
async def admin_export_json(actor_telegram_user_id: int = Query(...)):
    if not is_admin(actor_telegram_user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")

    profiles = list_all_profiles()
    return ProfilesExportResponse(
        total=len(profiles),
        profiles=profiles,
    )


@app.patch("/admin/users/{telegram_user_id}", response_model=ProfileResponse)
async def admin_patch_user(
    telegram_user_id: int,
    profile_update: ProfileUpdate,
    actor_telegram_user_id: int = Query(...),
):
    if not is_admin(actor_telegram_user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")

    if not user_exists(telegram_user_id):
        raise HTTPException(status_code=404, detail="Profile not found.")

    updated_profile = update_user_profile(telegram_user_id, profile_update)
    if updated_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return updated_profile


@app.delete("/admin/users/{telegram_user_id}", response_model=MessageResponse)
async def admin_delete_user(
    telegram_user_id: int,
    payload: ActorRequest,
):
    if not is_admin(payload.actor_telegram_user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")

    deleted = delete_user_profile(telegram_user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return MessageResponse(message="Profile deleted successfully by admin.")


@app.delete("/admin/redis/flush", response_model=MessageResponse)
async def admin_flush_redis(payload: ActorRequest):
    if not is_admin(payload.actor_telegram_user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")

    flush_all_project_data()
    return MessageResponse(message="All project data has been deleted from Redis.")


@app.get("/artists/tags", response_model=TagListResponse)
async def get_artist_tags():
    tags = list_all_tags()
    return TagListResponse(
        total=len(tags),
        tags=tags,
    )


@app.get("/artists/by-tag/{tag}", response_model=ProfilesByTagResponse)
async def get_artists_by_tag(tag: str):
    normalized = normalize_tag(tag)
    if not normalized:
        raise HTTPException(status_code=400, detail="Tag must not be empty.")

    profiles = get_profiles_by_tag(normalized)

    return ProfilesByTagResponse(
        tag=normalized,
        total=len(profiles),
        profiles=profiles,
    )