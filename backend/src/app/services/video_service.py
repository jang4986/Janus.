"""Nghiệp vụ video: tải lên, truy vấn, kết quả AI và phát tệp."""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.media import validate_mp4_content
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
    VideoUpdate,
)
from app.services.storage_service import StorageService, get_storage_service


def can_access_video(video: Video, requester: User | None) -> bool:
    """Kiểm tra quyền truy cập video: video public/published hoặc requester là chủ video / mod / admin."""
    video_status = getattr(video.status, "value", video.status)
    video_visibility = getattr(video.visibility, "value", video.visibility)
    is_public = (video_status == VideoStatus.published.value or video_status == VideoStatus.published) and (
        video_visibility == VideoVisibility.public.value or video_visibility == VideoVisibility.public
    )
    if is_public:
        return True
    if requester is None:
        return False
    is_owner = video.owner_id == requester.id
    user_role = getattr(requester.role, "value", requester.role)
    is_staff = user_role in {
        UserRole.moderator.value,
        UserRole.admin.value,
        UserRole.moderator,
        UserRole.admin,
    }
    return is_owner or is_staff


def get_video_stream_url(video: Video, storage: StorageService | None = None) -> str:
    """Sinh URL stream phù hợp dựa trên storage driver (S3 public/presigned hoặc API streaming endpoint)."""
    if storage is None:
        storage = get_storage_service()
    if storage.is_s3 and not storage.is_existing_local_path(video.storage_path):
        return storage.get_stream_url(video.storage_path, public=True)
    return f"/api/v1/videos/{video.id}/stream"


def resolve_video_thumbnail(
    db: Session, video_id: UUID, requester: User | None
) -> Path | str:
    """Kiểm tra quyền truy cập và giải quyết đường dẫn file hoặc URL thumbnail."""
    video = db.get(Video, video_id)
    if video is None or video.is_deleted:
        raise NotFoundError("Không tìm thấy ảnh bìa")
    if not can_access_video(video, requester):
        raise NotFoundError("Không tìm thấy ảnh bìa")

    storage = get_storage_service()
    thumbnail_key = storage.build_thumbnail_key(video_id)
    if storage.is_s3:
        thumbnail_url = storage.get_thumbnail_url(thumbnail_key)
        if thumbnail_url.startswith("/api/v1/videos/"):
            try:
                with storage.download_to_temp(video.storage_path) as video_path:
                    from app.services.thumbnail_service import extract_first_frame
                    thumbnail = extract_first_frame(video_path)
                storage.upload_thumbnail(thumbnail_key, thumbnail)
                thumbnail_url = storage.get_thumbnail_url(thumbnail_key)
            except Exception as exc:
                raise NotFoundError("Không thể tạo ảnh xem trước cho video này") from exc
        return thumbnail_url

    path = Path(get_settings().upload_dir) / thumbnail_key
    if not path.is_file():
        try:
            with storage.download_to_temp(video.storage_path) as video_path:
                from app.services.thumbnail_service import extract_first_frame
                thumbnail = extract_first_frame(video_path)
            storage.upload_thumbnail(thumbnail_key, thumbnail)
        except Exception as exc:
            raise NotFoundError("Không thể tạo ảnh xem trước cho video này") from exc
    return path



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
            stream_url=get_video_stream_url(video, storage),
            thumbnail_url=storage.get_thumbnail_url(
                storage.build_thumbnail_key(video.id)
            ),
            allow_comments=video.allow_comments,
            created_at=video.created_at,
            view_count=getattr(video, "view_count", 0) or 0,
            owner_name=video.owner_name,
        )
        for video in items
    ]
    return FeedResponse(
        items=feed_items,
        has_more=has_more,
        next_cursor=items[-1].created_at if has_more and items else None,
    )


def get_ai_result(db: Session, video_id: UUID, requester: User) -> AIResultResponse:
    """Chỉ chủ video hoặc moderator/admin xem được kết quả phân tích (ủy quyền sang ai_service)."""
    from app.services import ai_service
    return ai_service.get_ai_result(db, video_id, requester)


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
    if not can_access_video(video, requester):
        raise NotFoundError("Không tìm thấy video")
    storage = get_storage_service()
    if storage.is_s3 and not storage.is_existing_local_path(video.storage_path):
        is_public = (
            video.status == VideoStatus.published
            and video.visibility == VideoVisibility.public
        )
        return storage.get_stream_url(video.storage_path, public=is_public)
    path = Path(video.storage_path)
    if not path.is_file():
        raise NotFoundError("Không tìm thấy tệp video")
    return path

    if storage.is_s3 and not storage.is_existing_local_path(video.storage_path):
        return storage.get_stream_url(video.storage_path, public=is_public)
    path = Path(video.storage_path)
    if not path.is_file():
        raise NotFoundError("Không tìm thấy tệp video")
    return path
