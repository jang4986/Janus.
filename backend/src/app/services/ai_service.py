import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.base import SAFE_LABEL, AnalysisReport, DetectorUnavailableError
from app.ai.pipeline import analyse_video
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.exceptions import NotFoundError
from app.models import (
    AIJob,
    JobStatus,
    Label,
    LabelSource,
    ModerationAction,
    ModerationReview,
    User,
    UserRole,
    Video,
    VideoLabel,
    VideoStatus,
)
from app.schemas import AIResultResponse
from app.services.storage_service import get_storage_service
from app.services.thumbnail_service import extract_first_frame

logger = logging.getLogger(__name__)

MOCK_TRANSCRIPT = "Mock transcript for development testing."



def confidence_level(score: float) -> str:
    settings = get_settings()
    if score < settings.low_confidence_threshold:
        return "LOW"
    if score < settings.high_confidence_threshold:
        return "MEDIUM"
    return "HIGH"


def _upsert_label(db: Session, name: str) -> Label:
    label = db.scalar(select(Label).where(Label.name == name))
    if label is None:
        try:
            with db.begin_nested():
                label = Label(name=name)
                db.add(label)
                db.flush()
        except IntegrityError:
            label = db.scalar(select(Label).where(Label.name == name))
            if label is None:
                raise
    return label


def _apply_mock_result(db: Session, job: AIJob, video: Video, note: str | None = None) -> None:
    """Kết quả AI mô phỏng: transcript dev + nhãn Safe 0.95 và publish video."""
    job.transcript = MOCK_TRANSCRIPT
    job.error_message = note
    safe_label = _upsert_label(db, SAFE_LABEL)
    db.add(
        VideoLabel(
            video_id=video.id,
            label_id=safe_label.id,
            confidence=0.95,
            level=confidence_level(0.95),
            source=LabelSource.ai,
        )
    )
    job.status = JobStatus.succeeded
    job.completed_at = datetime.now(UTC)
    video.status = VideoStatus.published
    db.commit()


def _apply_analysis_report(db: Session, job: AIJob, video: Video, report: AnalysisReport) -> None:
    """Lưu kết quả từ pipeline NSFW-Detection vào job, nhãn và trạng thái video."""
    job.transcript = report.transcript
    has_high_risk = False
    has_medium_risk = False

    for detection in report.detections:
        level = confidence_level(detection.confidence)
        db.add(
            VideoLabel(
                video_id=video.id,
                label_id=_upsert_label(db, detection.label).id,
                confidence=detection.confidence,
                level=level,
                source=LabelSource.ai,
            )
        )
        if (
            detection.label.strip().lower() == "adult"
            or level == "HIGH"
            or detection.confidence >= 0.85
        ):
            has_high_risk = True
        elif level == "MEDIUM" or (0.4 <= detection.confidence < 0.85):
            has_medium_risk = True

    if report.is_safe and not has_high_risk and not has_medium_risk:
        # Trường hợp 3 - NỘI DUNG AN TOÀN (Safe / Low Risk) -> Phát hành ngay
        db.add(
            VideoLabel(
                video_id=video.id,
                label_id=_upsert_label(db, SAFE_LABEL).id,
                confidence=report.normal_confidence,
                level=confidence_level(report.normal_confidence),
                source=LabelSource.ai,
            )
        )
        video.status = VideoStatus.published
    elif has_high_risk:
        # Trường hợp 1 - VI PHẠM RÕ RÀNG (Adult / High Risk / confidence >= 0.85) -> Tự động từ chối
        video.status = VideoStatus.rejected
        auto_reject_note = "Tự động từ chối bởi hệ thống AI: Phát hiện nội dung vi phạm tiêu chuẩn (Adult)."
        db.add(
            ModerationReview(
                video_id=video.id,
                moderator_id=None,
                action=ModerationAction.reject,
                reason=auto_reject_note,
            )
        )
        if not job.error_message:
            job.error_message = auto_reject_note
    else:
        # Trường hợp 2 - RANH GIỚI NGHI VẤN (Borderline / Medium Risk) -> Chờ Moderator duyệt
        video.status = VideoStatus.pending_review
        pending_note = "Cần kiểm duyệt thủ công: Đang chờ Moderator xem xét."
        db.add(
            ModerationReview(
                video_id=video.id,
                moderator_id=None,
                action=None,
                reason=pending_note,
            )
        )
        if not job.error_message:
            job.error_message = pending_note

    job.status = JobStatus.succeeded
    job.completed_at = datetime.now(UTC)
    db.commit()


def _run_job(video_id: UUID, handler) -> None:
    """Vòng đời chung của một job AI: running -> handler -> succeeded/failed."""
    db = SessionLocal()
    job: AIJob | None = None
    video: Video | None = None
    try:
        job = db.scalar(
            select(AIJob)
            .where(AIJob.video_id == video_id)
            .order_by(AIJob.created_at.desc())
        )
        video = db.get(Video, video_id)
        if job is None or video is None:
            return
        job.status = JobStatus.running
        db.commit()
        handler(db, job, video)
    except Exception as exc:
        db.rollback()
        logger.exception("Job AI cho video %s thất bại", video_id)
        if job is not None:
            job.status = JobStatus.failed
            job.error_message = str(exc)
            if video is not None:
                video.status = VideoStatus.failed
            db.commit()
    finally:
        db.close()


def run_video_analysis(video_id: UUID) -> None:
    """Điểm vào của BackgroundTasks: chạy NSFW-Detection theo ``AI_ANALYSIS_MODE``."""

    def handler(db: Session, job: AIJob, video: Video) -> None:
        settings = get_settings()
        mode = settings.ai_analysis_mode.strip().lower()
        if mode not in {"auto", "required", "off"}:
            raise ValueError(
                f"AI_ANALYSIS_MODE không hợp lệ: {settings.ai_analysis_mode!r}"
            )

        report: AnalysisReport | None = None
        storage = get_storage_service()
        try:
            with storage.download_to_temp(video.storage_path) as path:
                try:
                    thumbnail = extract_first_frame(path)
                    storage.upload_thumbnail(
                        storage.build_thumbnail_key(video.id),
                        thumbnail,
                    )
                except Exception:
                    logger.exception("Không tạo được thumbnail cho video %s", video.id)
                if mode != "off":
                    try:
                        report = analyse_video(path)
                    except DetectorUnavailableError as exc:
                        if mode == "required":
                            raise
                        logger.warning(
                            "NSFW-Detection chưa sẵn sàng, dùng kết quả mock: %s", exc
                        )
                        note = f"[NSFW-Detection chưa sẵn sàng: {exc}]"
                        _apply_mock_result(db, job, video, note)
                        return
        except Exception:
            if mode != "off":
                raise
            logger.exception(
                "Không đọc được file video %s, dùng kết quả mock", video.id
            )

        if report is None:
            _apply_mock_result(db, job, video)
            return
        _apply_analysis_report(db, job, video, report)

    _run_job(video_id, handler)


def get_ai_result(db: Session, video_id: UUID, requester: User) -> AIResultResponse:
    """Chỉ chủ video hoặc moderator/admin xem được kết quả phân tích."""
    video = db.get(Video, video_id)
    allowed_roles = {UserRole.moderator, UserRole.admin}
    if (
        video is None
        or video.is_deleted
        or (video.owner_id != requester.id and requester.role not in allowed_roles)
    ):
        raise NotFoundError("Không tìm thấy video")
    job = db.scalar(
        select(AIJob)
        .where(AIJob.video_id == video_id)
        .order_by(AIJob.created_at.desc())
    )
    from app.services.video_label_service import to_label_responses
    labels = to_label_responses(video)
    return AIResultResponse(
        video_id=video_id,
        job_status=job.status.value if job else "unknown",
        transcript=job.transcript if job else None,
        error_message=job.error_message if job else None,
        labels=labels,
        video_status=video.status,
    )


# Backwards compatibility re-exports (chuyển sang đúng service domain)
from app.core.security import as_aware  # noqa: F401
from app.services.auth_service import (  # noqa: F401
    issue_refresh_token,
    purge_expired_revoked_tokens,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
)
from app.services.storage_service import remove_local_file  # noqa: F401

