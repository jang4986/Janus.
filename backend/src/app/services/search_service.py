"""Public search queries."""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.exceptions import InvalidInputError
from app.models import Label, User, Video, VideoLabel, VideoLike, VideoStatus, VideoVisibility
from app.schemas import SearchTagAuthor, SearchTagItem, SearchTagResponse
from app.services.storage_service import get_storage_service

SEARCH_LIMIT = 50


def search_videos_by_tag(db: Session, tag: str) -> list[Video]:
    tag = tag.strip()
    if not tag:
        raise InvalidInputError("Tag không được để trống")
    query = (
        select(Video)
        .join(VideoLabel, VideoLabel.video_id == Video.id)
        .join(Label, Label.id == VideoLabel.label_id)
        .options(selectinload(Video.owner))
        .where(
            Video.status == VideoStatus.published,
            Video.is_deleted.is_(False),
            Video.visibility == VideoVisibility.public,
            Label.is_active.is_(True),
            Label.name.ilike(f"%{tag}%"),
        )
        .distinct()
        .order_by(Video.created_at.desc())
        .limit(SEARCH_LIMIT)
    )
    return list(db.scalars(query))


def search_published_videos_by_tag(
    db: Session, tag: str, *, limit: int, cursor: datetime | None = None
) -> SearchTagResponse:
    normalized_tag = tag.strip().lstrip("#").strip()
    if not normalized_tag:
        raise InvalidInputError("Tag không được để trống")

    matching_label_ids = (
        select(VideoLabel.video_id)
        .join(Label, Label.id == VideoLabel.label_id)
        .where(
            Label.is_active.is_(True),
            Label.name.ilike(f"%{normalized_tag}%"),
        )
        .scalar_subquery()
    )
    conditions = [
        or_(Video.id.in_(matching_label_ids), Video.caption.ilike(f"%{normalized_tag}%")),
        Video.status == VideoStatus.published,
        Video.visibility == VideoVisibility.public,
        Video.is_deleted.is_(False),
    ]
    if cursor is not None:
        conditions.append(Video.created_at < cursor)

    like_count = (
        select(func.count())
        .select_from(VideoLike)
        .where(VideoLike.video_id == Video.id)
        .correlate(Video)
        .scalar_subquery()
    )
    videos = list(
        db.execute(
            select(Video, like_count)
            .options(selectinload(Video.owner))
            .where(*conditions)
            .order_by(Video.created_at.desc())
            .limit(limit + 1)
        )
    )
    has_more = len(videos) > limit
    rows = videos[:limit]
    if not rows:
        return SearchTagResponse(items=[], has_more=False, next_cursor=None)

    video_ids = [video.id for video, _ in rows]
    matched_rows = db.execute(
        select(VideoLabel.video_id, Label.name)
        .join(Label, Label.id == VideoLabel.label_id)
        .where(
            VideoLabel.video_id.in_(video_ids),
            Label.is_active.is_(True),
            Label.name.ilike(f"%{normalized_tag}%"),
        )
    ).all()
    matched_by_video: dict[object, list[str]] = {}
    for video_id, label_name in matched_rows:
        matched_by_video.setdefault(video_id, []).append(label_name)

    storage = get_storage_service()
    items = [
        SearchTagItem(
            id=video.id,
            caption=video.caption,
            thumbnail_url=storage.get_thumbnail_url(
                f"thumbnails/first-frame/{video.id}.jpg"
            ),
            stream_url=(
                storage.get_stream_url(video.storage_path, public=True)
                if storage.is_s3
                and not storage.is_existing_local_path(video.storage_path)
                else f"/api/v1/videos/{video.id}/stream"
            ),
            like_count=like_count_value,
            author=SearchTagAuthor(
                id=video.owner.id,
                username=(
                    f"{video.owner.display_name}#{video.owner.discriminator}"
                ),
                avatar_url=video.owner.avatar_url,
            ),
            matched_labels=matched_by_video.get(video.id, []),
            created_at=video.created_at,
        )
        for video, like_count_value in rows
    ]
    return SearchTagResponse(
        items=items,
        has_more=has_more,
        next_cursor=items[-1].created_at if has_more else None,
    )


def search_users(db: Session, query_text: str) -> list[User]:
    query_text = query_text.strip()
    if not query_text:
        raise InvalidInputError("Từ khóa tìm kiếm không được để trống")
    query = select(User).where(User.is_active.is_(True))
    if "#" in query_text:
        display_name, discriminator = query_text.rsplit("#", 1)
        if not discriminator.isdigit() or len(discriminator) != 4:
            raise InvalidInputError("Discriminator phải gồm 4 chữ số")
        if display_name:
            query = query.where(
                User.display_name == display_name,
                User.discriminator == discriminator,
            )
        else:
            query = query.where(User.discriminator == discriminator)
    else:
        query = query.where(User.display_name.ilike(f"%{query_text}%"))
    return list(
        db.scalars(
            query.order_by(User.display_name.asc(), User.discriminator.asc()).limit(
                SEARCH_LIMIT
            )
        )
    )
