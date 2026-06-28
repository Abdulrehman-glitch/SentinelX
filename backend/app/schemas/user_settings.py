import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Theme = Literal["dark", "light", "system"]
Density = Literal["comfortable", "compact"]
FontSize = Literal["normal", "large"]


class UserSettingsResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    theme: str
    density: str
    font_size: str
    reduce_motion: bool
    high_contrast: bool
    color_blind_mode: bool
    table_page_size: int
    auto_refresh_seconds: int
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class UserSettingsUpdateRequest(BaseModel):
    theme: Theme | None = None
    density: Density | None = None
    font_size: FontSize | None = None
    reduce_motion: bool | None = None
    high_contrast: bool | None = None
    color_blind_mode: bool | None = None
    table_page_size: int | None = Field(default=None, ge=5, le=100)
    auto_refresh_seconds: int | None = Field(default=None, ge=5, le=3600)