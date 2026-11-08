from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import LabelSource, VideoStatus, VideoVisibility


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    caption: str | None
    visibility: VideoVisibility
    allow_comments: bool
    size_bytes: int
    status: VideoStatus
    created_at: datetime
    owner_name: str | None = None
    view_count: int = 0


class FeedItem(BaseModel):
    id: UUID
    caption: str | None
    stream_url: str
    thumbnail_url: str | None
    allow_comments: bool
    created_at: datetime
    view_count: int = 0
    owner_name: str | None = None


class VideoViewResponse(BaseModel):
    video_id: UUID
    view_count: int
    counted: bool


class FeedResponse(BaseModel):
    items: list[FeedItem]
    has_more: bool
    next_cursor: datetime | None


class SearchTagAuthor(BaseModel):
    id: UUID
    username: str
    avatar_url: str | None


class SearchTagItem(BaseModel):
    id: UUID
    caption: str | None
    thumbnail_url: str | None
    stream_url: str
    like_count: int
    author: SearchTagAuthor
    matched_labels: list[str]
    created_at: datetime


class SearchTagResponse(BaseModel):
    items: list[SearchTagItem]
    has_more: bool
    next_cursor: datetime | None


class LabelResponse(BaseModel):
    name: str
    confidence: float
    level: str
    source: LabelSource = LabelSource.ai


class VideoUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=500)
    visibility: VideoVisibility | None = None
    allow_comments: bool | None = None

    @field_validator("caption")
    @classmethod
    def normalize_caption(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ConfirmLabelsRequest(BaseModel):
    labels: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("labels")
    @classmethod
    def normalize_labels(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            label = value.strip().lstrip("#").strip()
            if not label:
                raise ValueError("Nhãn không được để trống")
            if len(label) > 80:
                raise ValueError("Nhãn không được vượt quá 80 ký tự")
            key = label.casefold()
            if key not in seen:
                seen.add(key)
                normalized.append(label)
        return normalized


class VideoLabelsResponse(BaseModel):
    video: VideoResponse
    labels: list[LabelResponse]
    moderation_required: bool


class AIResultResponse(BaseModel):
    video_id: UUID
    job_status: str
    transcript: str | None
    error_message: str | None = None
    labels: list[LabelResponse]
    video_status: VideoStatus | None = None
