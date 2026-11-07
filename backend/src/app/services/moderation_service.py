"""Nghiệp vụ báo cáo, khiếu nại và kiểm duyệt."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.exceptions import ConflictError, InvalidInputError, NotFoundError
from app.models import (
    Appeal,
    AppealStatus,
    ModerationAction,
    ModerationReview,
    Report,
    ReportStatus,
    User,
    Video,
    VideoLabel,
    VideoStatus,
    utcnow,
)
from app.schemas.moderation import ModerationQueueItemResponse
from app.schemas.video import LabelResponse
from app.services.storage_service import get_storage_service


def create_report(db: Session, video_id: UUID, reporter: User, reason: str) -> Report:
    """Người dùng báo cáo video; mỗi người chỉ báo cáo mỗi video một lần (409)."""
    video = db.get(Video, video_id)
    if video is None or video.is_deleted:
        raise NotFoundError("Không tìm thấy video")
    existing = db.scalar(
        select(Report).where(
            Report.video_id == video_id,
            Report.reporter_id == reporter.id,
            Report.status == ReportStatus.open,
        )
    )
    if existing is not None:
        raise ConflictError("Bạn đã báo cáo video này")
    report = Report(video_id=video_id, reporter_id=reporter.id, reason=reason)
    if video.status == VideoStatus.published:
        video.status = VideoStatus.pending_review
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def moderation_queue(db: Session) -> list[ModerationQueueItemResponse]:
    storage = get_storage_service()
    videos = list(
        db.scalars(
            select(Video)
            .options(
                selectinload(Video.owner),
                selectinload(Video.labels).selectinload(VideoLabel.label),
                selectinload(Video.reports),
                selectinload(Video.ai_jobs),
            )
            .where(Video.status == VideoStatus.pending_review, Video.is_deleted.is_(False))
            .order_by(Video.created_at)
        )
    )
    items: list[ModerationQueueItemResponse] = []
    for video in videos:
        open_reports = [r for r in video.reports if r.status == ReportStatus.open]
        report_count = len(open_reports)

        latest_job = video.ai_jobs[0] if video.ai_jobs else None
        ai_status = latest_job.status.value if latest_job else None

        labels = [
            LabelResponse(
                name=vl.label.name,
                confidence=vl.confidence,
                level=vl.level,
                source=vl.source,
            )
            for vl in video.labels
            if vl.label is not None
        ]

        borderline_labels = [
            l
            for l in video.labels
            if l.label and (l.label.name.lower() != "safe" or l.level in ("MEDIUM", "HIGH"))
        ]
        if borderline_labels:
            top_label = max(borderline_labels, key=lambda l: l.confidence)
            conf_pct = round(top_label.confidence * 100)
            if report_count > 0:
                queue_reason = f"AI nghi vấn ({top_label.label.name} {conf_pct}%) & {report_count} báo cáo"
            else:
                queue_reason = f"AI nghi vấn vi phạm ({top_label.label.name} {conf_pct}%)"
        elif report_count > 0:
            sample_reason = open_reports[0].reason.strip()
            if len(sample_reason) > 40:
                sample_reason = sample_reason[:37] + "..."
            queue_reason = f"Bị người dùng báo cáo ({report_count} lượt: {sample_reason})"
        else:
            queue_reason = "Chờ kiểm duyệt thủ công"

        stream_url = (
            storage.get_stream_url(video.storage_path, public=True)
            if storage.is_s3 and not storage.is_existing_local_path(video.storage_path)
            else f"/api/v1/videos/{video.id}/stream"
        )
        thumbnail_url = storage.get_thumbnail_url(
            f"thumbnails/first-frame/{video.id}.jpg"
        )

        item = ModerationQueueItemResponse(
            id=video.id,
            original_filename=video.original_filename,
            caption=video.caption,
            visibility=video.visibility,
            allow_comments=video.allow_comments,
            size_bytes=video.size_bytes,
            status=video.status,
            created_at=video.created_at,
            owner_name=video.owner.display_name if video.owner else None,
            thumbnail_url=thumbnail_url,
            stream_url=stream_url,
            ai_status=ai_status,
            labels=labels,
            queue_reason=queue_reason,
            report_count=report_count,
        )
        items.append(item)
    return items


def decide_video(db: Session, video_id: UUID, moderator: User, action: ModerationAction, reason: str | None) -> None:
    video = db.get(Video, video_id)
    if video is None or video.is_deleted:
        raise NotFoundError("Không tìm thấy video")
    if action == ModerationAction.reject and (not reason or not reason.strip()):
        raise InvalidInputError("Lý do từ chối là bắt buộc.")
    clean_reason = reason.strip() if reason else None
    video.status = VideoStatus.published if action == ModerationAction.approve else VideoStatus.rejected
    db.add(
        ModerationReview(
            video_id=video.id,
            moderator_id=moderator.id,
            action=action,
            reason=clean_reason,
        )
    )
    db.commit()


def list_open_reports(db: Session) -> list[Report]:
    return list(
        db.scalars(
            select(Report).where(Report.status == ReportStatus.open).order_by(Report.created_at)
        )
    )


def get_moderator_profile_stats(db: Session, moderator: User) -> dict[str, int]:
    decisions_count = db.scalar(
        select(func.count(ModerationReview.id)).where(
            ModerationReview.moderator_id == moderator.id
        )
    ) or 0
    rejected_videos_count = db.scalar(
        select(func.count(func.distinct(Video.id)))
        .join(ModerationReview, ModerationReview.video_id == Video.id)
        .where(
            ModerationReview.moderator_id == moderator.id,
            Video.status == VideoStatus.rejected,
            Video.is_deleted.is_(False),
        )
    ) or 0
    open_reports_count = db.scalar(
        select(func.count(Report.id)).where(Report.status == ReportStatus.open)
    ) or 0
    handled_appeals_count = db.scalar(
        select(func.count(Appeal.id)).where(
            Appeal.moderator_id == moderator.id,
            Appeal.status != AppealStatus.open,
        )
    ) or 0
    return {
        "decisions_count": decisions_count,
        "rejected_videos_count": rejected_videos_count,
        "open_reports_count": open_reports_count,
        "handled_appeals_count": handled_appeals_count,
    }


def decide_report(db: Session, report_id: UUID, moderator: User, action: ModerationAction, reason: str | None) -> None:
    """Quyết định báo cáo: approve = video vi phạm (ẩn video), reject = bỏ báo cáo."""
    report = db.get(Report, report_id)
    if report is None or report.status != ReportStatus.open:
        raise NotFoundError("Không tìm thấy báo cáo đang chờ xử lý")
    video = db.get(Video, report.video_id)
    if video is None:
        raise NotFoundError("Không tìm thấy video liên quan")
    report.status = ReportStatus.resolved if action == ModerationAction.reject else ReportStatus.rejected
    video.status = VideoStatus.rejected if action == ModerationAction.approve else VideoStatus.published
    db.add(
        ModerationReview(
            video_id=video.id,
            moderator_id=moderator.id,
            action=action,
            reason=reason,
        )
    )
    db.commit()


def create_appeal(db: Session, video_id: UUID, user: User, reason: str) -> Appeal:
    """Chủ video gửi khiếu nại đối với video bị từ chối (UC011)."""
    video = db.get(Video, video_id)
    if video is None or video.is_deleted or video.owner_id != user.id:
        raise NotFoundError("Không tìm thấy video")
    if video.status != VideoStatus.rejected:
        raise InvalidInputError("Chỉ có thể khiếu nại video đã bị từ chối")
    existing_open = db.scalar(
        select(Appeal).where(
            Appeal.video_id == video_id,
            Appeal.status == AppealStatus.open,
        )
    )
    if existing_open is not None:
        raise ConflictError("Video này đã có khiếu nại đang chờ xử lý")

    appeal = Appeal(
        video_id=video_id,
        user_id=user.id,
        reason=reason,
        status=AppealStatus.open,
    )
    db.add(appeal)
    db.commit()
    db.refresh(appeal)
    return appeal


def list_appeals(db: Session, status: AppealStatus | None = AppealStatus.open) -> list[Appeal]:
    """Lấy danh sách các khiếu nại (mặc định các khiếu nại đang mở) (UC017)."""
    query = select(Appeal).options(selectinload(Appeal.user))
    if status is not None:
        query = query.where(Appeal.status == status)
    query = query.order_by(Appeal.created_at.desc())
    return list(db.scalars(query))


def decide_appeal(
    db: Session,
    appeal_id: UUID,
    moderator: User,
    action: ModerationAction,
    reason: str | None,
) -> None:
    """Xử lý phán quyết khiếu nại (UC017)."""
    appeal = db.get(Appeal, appeal_id)
    if appeal is None:
        raise NotFoundError("Không tìm thấy khiếu nại")
    if appeal.status != AppealStatus.open:
        raise ConflictError("Khiếu nại đã được xử lý")

    video = db.get(Video, appeal.video_id)
    if video is None or video.is_deleted:
        raise NotFoundError("Không tìm thấy video liên quan")

    if action == ModerationAction.approve:
        appeal.status = AppealStatus.approved
        video.status = VideoStatus.published
    else:
        appeal.status = AppealStatus.rejected

    appeal.moderator_id = moderator.id
    appeal.decision_reason = reason
    appeal.decided_at = utcnow()

    db.add(
        ModerationReview(
            video_id=video.id,
            moderator_id=moderator.id,
            action=action,
            reason=f"Phán quyết khiếu nại: {reason}" if reason else "Phán quyết khiếu nại",
        )
    )
    db.commit()
