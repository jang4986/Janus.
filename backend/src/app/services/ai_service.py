import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.base import SAFE_LABEL, AnalysisReport, DetectorUnavailableError
from app.ai.pipeline import analyse_video
from app.core.config import get_settings
from app.core.security import hash_opaque_token, new_opaque_token
from app.db.session import SessionLocal
from app.models import (
    AIJob,
    JobStatus,
    Label,
    LabelSource,
    ModerationAction,
    ModerationReview,
    User,
    Video,
    VideoLabel,
    VideoStatus,
)
from app.services.storage_service import get_storage_service
from app.services.thumbnail_service import extract_first_frame

logger = logging.getLogger(__name__)

SUPPORTED_MP4_CODECS = (b"avc1", b"hvc1", b"hev1", b"av01", b"mp4v")
SUPPORTED_MP4_BRANDS = (
    b"isom",
    b"iso2",
    b"iso4",
    b"iso5",
    b"iso6",
    b"mp41",
    b"mp42",
    b"mmp4",
    b"M4V ",
    b"M4A ",
    b"dash",
    b"avc1",
    b"MSNV",
    b"qt  ",
)
MOCK_TRANSCRIPT = "Mock transcript for development testing."


def validate_mp4_content(content: bytes) -> str:
    if len(content) < 16 or content[4:8] != b"ftyp":
        raise ValueError("Tệp không có MP4 magic bytes hợp lệ")
    box_size = int.from_bytes(content[0:4], "big")
    if box_size < 16 or box_size > len(content):
        raise ValueError("MP4 ftyp box không hợp lệ")
    compatible_brands = content[8:box_size]
    has_known_brand = any(brand in compatible_brands for brand in SUPPORTED_MP4_BRANDS)
    if not has_known_brand:
        # Nếu không nằm trong danh sách tường minh, kiểm tra major_brand có phải 4 ký tự ASCII hợp lệ của container MP4 chuẩn
        major_brand = content[8:12]
        if not (len(major_brand) == 4 and all(32 <= b <= 126 for b in major_brand)):
            raise ValueError("MP4 brand không được hỗ trợ")
    codec = next((marker for marker in SUPPORTED_MP4_CODECS if marker in content), None)
    if codec is None:
        raise ValueError("Không tìm thấy codec video MP4 được hỗ trợ")
    return codec.decode("ascii")


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
    job.completed_at = datetime.now(timezone.utc)
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
    job.completed_at = datetime.now(timezone.utc)
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


def run_mock_analysis(video_id: UUID, note: str | None = None) -> None:
    """Giữ nguyên hành vi mock cũ (dùng khi AI bị tắt hoặc môi trường AI chưa sẵn sàng)."""

    def handler(db: Session, job: AIJob, video: Video) -> None:
        try:
            storage = get_storage_service()
            with storage.download_to_temp(video.storage_path) as path:
                thumbnail = extract_first_frame(path)
            storage.upload_thumbnail(f"thumbnails/first-frame/{video.id}.jpg", thumbnail)
        except Exception:
            logger.exception("Không tạo được thumbnail cho video %s", video.id)
        _apply_mock_result(db, job, video, note)

    _run_job(video_id, handler)


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
        with get_storage_service().download_to_temp(video.storage_path) as path:
            thumbnail = extract_first_frame(path)
            get_storage_service().upload_thumbnail(
                f"thumbnails/first-frame/{video.id}.jpg",
                thumbnail,
            )
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

        if report is None:
            _apply_mock_result(db, job, video)
            return
        _apply_analysis_report(db, job, video, report)

    _run_job(video_id, handler)


def remove_local_file(path: str) -> None:
    Path(path).unlink(missing_ok=True)


def as_aware(value: datetime) -> datetime:
    """SQLite trả datetime naive; chuẩn hoá về UTC để so sánh an toàn."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def issue_refresh_token(db: Session, user: User) -> str:
    """Tạo refresh token mới (chỉ lưu băm) và trả về giá trị thô cho client."""
    settings = get_settings()
    raw = new_opaque_token(48)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    return raw


def revoke_refresh_token(db: Session, raw_token: str, user_id: UUID | None = None) -> bool:
    """Thu hồi một refresh token; trả về True nếu tìm thấy và còn hiệu lực."""
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_opaque_token(raw_token)))
    if row is None or row.revoked_at is not None:
        return False
    if user_id is not None and row.user_id != user_id:
        return False
    row.revoked_at = datetime.now(timezone.utc)
    return True


def revoke_all_refresh_tokens(db: Session, user_id: UUID) -> None:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    )
    for row in rows:
        row.revoked_at = now


def purge_expired_revoked_tokens(db: Session) -> None:
    """Dọn access token đã hết hạn khỏi bảng thu hồi."""
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc)))
