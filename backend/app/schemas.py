from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


CommissionStatus = Literal["open", "closed"]


class ProfileCreate(BaseModel):
    telegram_user_id: int
    display_name: str = Field(..., min_length=1, max_length=100)
    artist_name: str = Field(..., min_length=1, max_length=100)

    username: str | None = Field(default=None, max_length=100)
    short_bio: str | None = Field(default=None, max_length=500)
    portfolio_link: str | None = Field(default=None, max_length=255)
    contact_info: str | None = Field(default=None, max_length=255)
    commission_status: CommissionStatus = "closed"
    tags: list[str] = Field(default_factory=list)
    price_range: str | None = Field(default=None, max_length=100)


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    artist_name: str | None = Field(default=None, min_length=1, max_length=100)

    username: str | None = Field(default=None, max_length=100)
    short_bio: str | None = Field(default=None, max_length=500)
    portfolio_link: str | None = Field(default=None, max_length=255)
    contact_info: str | None = Field(default=None, max_length=255)
    commission_status: CommissionStatus | None = None
    tags: list[str] | None = None
    price_range: str | None = Field(default=None, max_length=100)


class ProfileResponse(BaseModel):
    telegram_user_id: int
    display_name: str
    artist_name: str

    username: str | None = None
    short_bio: str | None = None
    portfolio_link: str | None = None
    contact_info: str | None = None
    commission_status: CommissionStatus = "closed"
    tags: list[str] = Field(default_factory=list)
    price_range: str | None = None

    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class ExistsResponse(BaseModel):
    exists: bool


class AdminActivateRequest(BaseModel):
    telegram_user_id: int
    admin_code: str


class ActorRequest(BaseModel):
    actor_telegram_user_id: int


class DeleteProfileRequest(BaseModel):
    actor_telegram_user_id: int


class MessageResponse(BaseModel):
    message: str


class AdminActivateResponse(BaseModel):
    message: str
    telegram_user_id: int
    is_admin: bool


class ProfilesExportResponse(BaseModel):
    total: int
    profiles: list[ProfileResponse]


class TagListResponse(BaseModel):
    total: int
    tags: list[str]


class ProfilesByTagResponse(BaseModel):
    tag: str
    total: int
    profiles: list[ProfileResponse]