"""Nghiệp vụ like, bookmark, comment và follow."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.exceptions import (
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
)
from app.models import (
    User,
    UserFollow,
    UserRole,
    Video,
    VideoBookmark,
    VideoComment,
    VideoLike,
    VideoStatus,
)
from app.schemas import (
    BookmarkedVideosResponse,
    BookmarkResponse,
    CommentCreate,
    CommentsResponse,
    FollowResponse,
    LikeResponse,
    UsersResponse,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _require_regular_user(user: User) -> None:
    """Chỉ cho phép người dùng thông thường (role=user) thực hiện thao tác xã hội.
    Moderator và Admin không được like, bookmark, comment."""
    if user.role != UserRole.user:
        raise ForbiddenError("Chỉ người dùng thông thường mới được thực hiện thao tác này")


def _page(page: int, page_size: int) -> tuple[int, int, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return page, page_size, (page - 1) * page_size


def _published_video(db: Session, video_id: UUID) -> Video:
    video = db.scalar(
        select(Video).where(
            Video.id == video_id,
            Video.status == VideoStatus.published,
            Video.is_deleted.is_(False),
        )
    )
    if video is None:
        raise NotFoundError("Không tìm thấy video công khai")
    return video


def toggle_like(db: Session, video_id: UUID, user: User) -> LikeResponse:
    _require_regular_user(user)
    _published_video(db, video_id)
    like = db.get(VideoLike, {"video_id": video_id, "user_id": user.id})
    if like is None:
        db.add(VideoLike(video_id=video_id, user_id=user.id))
        is_liked = True
    else:
        db.delete(like)
        is_liked = False
    db.flush()
    count = db.scalar(
        select(func.count()).select_from(VideoLike).where(VideoLike.video_id == video_id)
    )
    db.commit()
    return LikeResponse(is_liked=is_liked, like_count=count or 0)


def toggle_bookmark(db: Session, video_id: UUID, user: User) -> BookmarkResponse:
    _require_regular_user(user)
    _published_video(db, video_id)
    bookmark = db.get(VideoBookmark, {"video_id": video_id, "user_id": user.id})
    if bookmark is None:
        db.add(VideoBookmark(video_id=video_id, user_id=user.id))
        is_bookmarked = True
    else:
        db.delete(bookmark)
        is_bookmarked = False
    db.commit()
    return BookmarkResponse(is_bookmarked=is_bookmarked)


def list_bookmarks(
    db: Session, user: User, page: int, page_size: int
) -> BookmarkedVideosResponse:
    page, page_size, offset = _page(page, page_size)
    base = (
        select(Video)
        .join(VideoBookmark, VideoBookmark.video_id == Video.id)
        .options(selectinload(Video.owner))
        .where(
            VideoBookmark.user_id == user.id,
            Video.status == VideoStatus.published,
            Video.is_deleted.is_(False),
        )
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.scalars(
            base.order_by(VideoBookmark.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
    )
    return BookmarkedVideosResponse(
        items=items, page=page, page_size=page_size, total=total
    )


def list_comments(
    db: Session, video_id: UUID, page: int, page_size: int
) -> CommentsResponse:
    _published_video(db, video_id)
    page, page_size, offset = _page(page, page_size)
    base = (
        select(VideoComment)
        .options(selectinload(VideoComment.author))
        .where(VideoComment.video_id == video_id, VideoComment.is_deleted.is_(False))
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.scalars(
            base.order_by(VideoComment.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
    )
    return CommentsResponse(items=items, page=page, page_size=page_size, total=total)


def create_comment(
    db: Session, video_id: UUID, user: User, payload: CommentCreate
) -> VideoComment:
    _require_regular_user(user)
    video = _published_video(db, video_id)
    if not video.allow_comments:
        raise ForbiddenError("Video hiện không cho phép bình luận")
    comment = VideoComment(
        video_id=video_id, author_id=user.id, content=payload.content.strip()
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    comment.author = user
    return comment


def delete_comment(db: Session, comment_id: UUID, user: User) -> None:
    comment = db.scalar(
        select(VideoComment).where(
            VideoComment.id == comment_id, VideoComment.is_deleted.is_(False)
        )
    )
    if comment is None:
        raise NotFoundError("Không tìm thấy bình luận")
    video = db.get(Video, comment.video_id)
    can_delete = (
        comment.author_id == user.id
        or (video is not None and video.owner_id == user.id)
        or user.role in {UserRole.moderator, UserRole.admin}
    )
    if not can_delete:
        raise ForbiddenError("Bạn không có quyền xóa bình luận này")
    comment.is_deleted = True
    comment.content = None
    db.commit()


def toggle_follow(db: Session, target_id: UUID, user: User) -> FollowResponse:
    if target_id == user.id:
        raise InvalidInputError("Không thể tự theo dõi chính mình")
    target = db.get(User, target_id)
    if target is None or not target.is_active:
        raise NotFoundError("Không tìm thấy người dùng")
    follow = db.get(
        UserFollow, {"follower_id": user.id, "following_id": target_id}
    )
    if follow is None:
        db.add(UserFollow(follower_id=user.id, following_id=target_id))
        is_following = True
    else:
        db.delete(follow)
        is_following = False
    db.commit()
    return FollowResponse(is_following=is_following)


def list_followers(
    db: Session, target_id: UUID, page: int, page_size: int
) -> UsersResponse:
    return _list_follow_users(db, target_id, page, page_size, following=False)


def list_following(
    db: Session, target_id: UUID, page: int, page_size: int
) -> UsersResponse:
    return _list_follow_users(db, target_id, page, page_size, following=True)


def _list_follow_users(
    db: Session, target_id: UUID, page: int, page_size: int, following: bool
) -> UsersResponse:
    target = db.get(User, target_id)
    if target is None or not target.is_active:
        raise NotFoundError("Không tìm thấy người dùng")
    page, page_size, offset = _page(page, page_size)
    join_column = UserFollow.follower_id if following else UserFollow.following_id
    user_column = UserFollow.following_id if following else UserFollow.follower_id
    base = select(User).join(UserFollow, user_column == User.id).where(
        join_column == target_id, User.is_active.is_(True)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.scalars(
            base.order_by(User.display_name, User.discriminator)
            .offset(offset)
            .limit(page_size)
        )
    )
    return UsersResponse(items=items, page=page, page_size=page_size, total=total)
