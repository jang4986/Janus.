from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AppealStatus, ModerationAction
from app.schemas.report import ReportResponse
from app.schemas.video import LabelResponse, VideoResponse


class ModerationDecisionRequest(BaseModel):
    action: ModerationAction
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_reason_if_rejected(self) -> "ModerationDecisionRequest":
        if self.action == ModerationAction.reject:
            if not self.reason or not self.reason.strip():
                raise ValueError("Lý do từ chối là bắt buộc.")
            self.reason = self.reason.strip()
        return self


class ModerationQueueItemResponse(VideoResponse):
    thumbnail_url: str | None = None
    stream_url: str | None = None
    ai_status: str | None = None
    labels: list[LabelResponse] = Field(default_factory=list)
    queue_reason: str = "Chờ duyệt"
    report_count: int = 0
    reports: list[ReportResponse] = Field(default_factory=list)


class AppealCreate(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class AppealDecisionRequest(BaseModel):
    action: ModerationAction
    reason: str | None = Field(default=None, max_length=1000)


class AppealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    video_id: UUID
    user_id: UUID
    reason: str
    status: AppealStatus
    moderator_id: UUID | None = None
    decision_reason: str | None = None
    created_at: datetime
    decided_at: datetime | None = None
    user_display_name: str | None = None


class ModeratorProfileStatsResponse(BaseModel):
    decisions_count: int = 0
    rejected_videos_count: int = 0
    open_reports_count: int = 0
    handled_appeals_count: int = 0


class VideoLabelItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ReplaceVideoLabelsRequest(BaseModel):
    labels: list[VideoLabelItem] = Field(default_factory=list)
