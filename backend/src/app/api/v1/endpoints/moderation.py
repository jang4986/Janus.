from uuid import UUID

from fastapi import APIRouter, status

from app.dependencies import DbSession, ModeratorUser
from app.models import Appeal, Report
from app.schemas import (
    AppealDecisionRequest,
    AppealResponse,
    ModerationDecisionRequest,
    ModerationQueueItemResponse,
    ModeratorProfileStatsResponse,
    ReportResponse,
)
from app.services import moderation_service

router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("/stats/me", response_model=ModeratorProfileStatsResponse)
def moderation_profile_stats(
    user: ModeratorUser,
    db: DbSession,
) -> dict[str, int]:
    return moderation_service.get_moderator_profile_stats(db, user)


@router.get("/queue", response_model=list[ModerationQueueItemResponse])
def moderation_queue(
    user: ModeratorUser,
    db: DbSession,
) -> list[ModerationQueueItemResponse]:
    return moderation_service.moderation_queue(db)


@router.post("/videos/{video_id}/decision", status_code=status.HTTP_204_NO_CONTENT)
def moderation_decision(
    video_id: UUID,
    payload: ModerationDecisionRequest,
    user: ModeratorUser,
    db: DbSession,
) -> None:
    moderation_service.decide_video(db, video_id, user, payload.action, payload.reason)


@router.get("/reports", response_model=list[ReportResponse])
def moderation_reports(
    user: ModeratorUser,
    db: DbSession,
) -> list[Report]:
    return moderation_service.list_open_reports(db)


@router.post("/reports/{report_id}/decision", status_code=status.HTTP_204_NO_CONTENT)
def report_decision(
    report_id: UUID,
    payload: ModerationDecisionRequest,
    user: ModeratorUser,
    db: DbSession,
) -> None:
    moderation_service.decide_report(db, report_id, user, payload.action, payload.reason)


@router.get("/appeals", response_model=list[AppealResponse])
def moderation_appeals(
    user: ModeratorUser,
    db: DbSession,
) -> list[Appeal]:
    return moderation_service.list_appeals(db)


@router.post("/appeals/{appeal_id}/decision", status_code=status.HTTP_204_NO_CONTENT)
def appeal_decision(
    appeal_id: UUID,
    payload: AppealDecisionRequest,
    user: ModeratorUser,
    db: DbSession,
) -> None:
    moderation_service.decide_appeal(db, appeal_id, user, payload.action, payload.reason)
