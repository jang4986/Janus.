from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.dependencies import CurrentUser, DbSession
from app.schemas import (
    BookmarkedVideosResponse,
    BookmarkResponse,
    CommentCreate,
    CommentResponse,
    CommentsResponse,
    FollowResponse,
    LikeResponse,
    UsersResponse,
)
from app.services import social_service

router = APIRouter(tags=["social"])


@router.post("/videos/{video_id}/like", response_model=LikeResponse)
def like_video(
    video_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> LikeResponse:
    return social_service.toggle_like(db, video_id, user)


@router.post("/videos/{video_id}/bookmark", response_model=BookmarkResponse)
def bookmark_video(
    video_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> BookmarkResponse:
    return social_service.toggle_bookmark(db, video_id, user)


@router.get("/users/me/bookmarks", response_model=BookmarkedVideosResponse)
def bookmarks(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BookmarkedVideosResponse:
    return social_service.list_bookmarks(db, user, page, page_size)


@router.get("/videos/{video_id}/comments", response_model=CommentsResponse)
def comments(
    video_id: UUID,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CommentsResponse:
    return social_service.list_comments(db, video_id, page, page_size)


@router.post(
    "/videos/{video_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    video_id: UUID,
    payload: CommentCreate,
    user: CurrentUser,
    db: DbSession,
) -> CommentResponse:
    return social_service.create_comment(db, video_id, user, payload)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_comment(
    comment_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> None:
    social_service.delete_comment(db, comment_id, user)


@router.post("/users/{user_id}/follow", response_model=FollowResponse)
def follow_user(
    user_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> FollowResponse:
    return social_service.toggle_follow(db, user_id, user)


@router.get("/users/{user_id}/followers", response_model=UsersResponse)
def followers(
    user_id: UUID,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UsersResponse:
    return social_service.list_followers(db, user_id, page, page_size)


@router.get("/users/{user_id}/following", response_model=UsersResponse)
def following(
    user_id: UUID,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UsersResponse:
    return social_service.list_following(db, user_id, page, page_size)
