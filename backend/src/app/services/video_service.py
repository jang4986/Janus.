"""Nghiệp vụ video: tải lên, truy vấn, kết quả AI và phát tệp."""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.exceptions import (
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    PayloadTooLargeError,
)
from app.models import (
    AIJob,
    User,
    UserRole,
    Video,
    VideoStatus,
    VideoVisibility,
)
from app.schemas import (
    AIResultResponse,
    FeedItem,
    FeedResponse,
    LabelResponse,
    VideoUpdate,
)
from app.services.ai_service import validate_mp4_content
from app.services.storage_service import get_storage_service


def upload_video(
    db: Session,
    *,
    owner: User,
    filename: str,
    content_type: str | None,
    content: bytes,
    caption: str | None,
) -> Video:
    """Kiểm tra tệp MP4, lưu vào thư mục upload và tạo job AI chờ xử lý."""
    settings = get_settings()
    if (
        Path(filename).suffix.lower() != settings.allowed_video_extension
        or content_type != "video/mp4"
    ):
        raise InvalidInputError("Chỉ chấp nhận tệp MP4")
    if len(content) > settings.max_upload_size_bytes:
        raise PayloadTooLargeError("Video vượt quá dung lượng 50MB")
    try:
        validate_mp4_content(content)
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc

    video = Video(
        owner_id=owner.id,
        original_filename=Path(filename).name,
        storage_path="",
        mime_type="video/mp4",
        size_bytes=len(content),
        caption=caption,
    )
    db.add(video)
    db.flush()
    storage = get_storage_service()
    object_key = f"videos/{video.id}.mp4"
    stored_path = storage.upload_file(object_key, content, "video/mp4")
    video.storage_path = stored_path
    db.add(AIJob(video_id=video.id))
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            storage.delete_file(stored_path)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Không thể dọn object video mồ côi %s", stored_path
            )
        raise
    db.refresh(video)
    return video


def list_owned_videos(db: Session, owner: User) -> list[Video]:
    return list(
        db.scalars(
            select(Video)
            .options(selectinload(Video.owner))
            .where(Video.owner_id == owner.id, Video.is_deleted.is_(False))
            .order_by(Video.created_at.desc())
        )
    )


def list_published_feed(
    db: Session, *, limit: int, cursor: datetime | None = None
) -> FeedResponse:
    conditions = [
        Video.status == VideoStatus.published,
        Video.is_deleted.is_(False),
        Video.visibility == VideoVisibility.public,
    ]
    if cursor is not None:
        conditions.append(Video.created_at < cursor)

    storage = get_storage_service()
    batch_size = max(limit + 1, 20)
    scan_cursor = cursor
    videos: list[Video] = []
    exhausted = False
    while len(videos) <= limit and not exhausted:
        batch_conditions = list(conditions)
        if scan_cursor is not None:
            batch_conditions.append(Video.created_at < scan_cursor)
        batch = list(
            db.scalars(
                select(Video)
                .options(selectinload(Video.owner))
                .where(*batch_conditions)
                .order_by(Video.created_at.desc())
                .limit(batch_size)
            )
        )
        if not batch:
            exhausted = True
            break

        scan_cursor = batch[-1].created_at
        if len(batch) < batch_size:
            exhausted = True
        videos.extend(
            video
            for video in batch
            if storage.is_s3
            or storage.is_existing_local_path(video.storage_path)
        )

    has_more = len(videos) > limit
    items = videos[:limit]
    feed_items = [
        FeedItem(
            id=video.id,
            caption=video.caption,
            stream_url=(
                storage.get_stream_url(video.storage_path, public=True)
                if storage.is_s3
                and not storage.is_existing_local_path(video.storage_path)
                else f"/api/v1/videos/{video.id}/stream"
            ),
            thumbnail_url=storage.get_thumbnail_url(
                f"thumbnails/first-frame/{video.id}.jpg"
            ),
            allow_comments=video.allow_comments,
            created_at=video.created_at,
            view_count=getattr(video, "view_count", 0) or 0,
        )
        for video in items
    ]
    return FeedResponse(
        items=feed_items,
        has_more=has_more,
        next_cursor=items[-1].created_at if has_more and items else None,
    )


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
    labels = [
        LabelResponse(
            name=item.label.name,
            confidence=item.confidence,
            level=item.level,
            source=item.source,
        )
        for item in video.labels
    ]
    return AIResultResponse(
        video_id=video_id,
        job_status=job.status.value if job else "unknown",
        transcript=job.transcript if job else None,
        error_message=job.error_message if job else None,
        labels=labels,
        video_status=video.status,
    )


def soft_delete_video(db: Session, video_id: UUID, owner: User) -> None:
    video = db.get(Video, video_id)
    if video is None or video.owner_id != owner.id:
        raise NotFoundError("Không tìm thấy video")
    video.is_deleted = True
    video.status = VideoStatus.deleted
    db.commit()


def update_video(
    db: Session, video_id: UUID, owner: User, payload: VideoUpdate
) -> Video:
    video = db.get(Video, video_id)
    if video is None or video.is_deleted:
        raise NotFoundError("Không tìm thấy video")
    if video.owner_id != owner.id:
        raise ForbiddenError("Bạn không có quyền chỉnh sửa video này")
    values = payload.model_dump(exclude_unset=True)
    if (
        video.status == VideoStatus.rejected
        and values.get("visibility") == VideoVisibility.public
    ):
        raise InvalidInputError("Video đã bị từ chối không thể chuyển sang công khai")
    if "caption" in values:
        video.caption = values["caption"]
    if "visibility" in values:
        video.visibility = values["visibility"]
    if "allow_comments" in values:
        video.allow_comments = values["allow_comments"]
    db.commit()
    db.refresh(video)
    return video


def resolve_stream_target(
    db: Session, video_id: UUID, requester: User | None
) -> Path | str:
    """Trả về đường dẫn tệp phát được: video published cho mọi người,
    còn lại chỉ chủ video hoặc moderator/admin."""
    video = db.get(Video, video_id)
    if video is None or video.is_deleted:
        raise NotFoundError("Không tìm thấy video")
    is_owner = requester is not None and video.owner_id == requester.id
    is_staff = requester is not None and requester.role in {
        UserRole.moderator,
        UserRole.admin,
    }
    is_public = (
        video.status == VideoStatus.published
        and video.visibility == VideoVisibility.public
    )
    if not is_public and not (is_owner or is_staff):
        raise NotFoundError("Không tìm thấy video")
    storage = get_storage_service()
    if storage.is_s3 and not storage.is_existing_local_path(video.storage_path):
        return storage.get_stream_url(video.storage_path, public=is_public)
    path = Path(video.storage_path)
    if not path.is_file():
        raise NotFoundError("Không tìm thấy tệp video")
    return path
