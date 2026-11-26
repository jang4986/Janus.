from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies import DbSession
from app.schemas import PublicUserResponse, SearchTagResponse, VideoResponse
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/videos-by-tag/grid", response_model=SearchTagResponse)
def videos_by_tag_grid(
    tag: Annotated[str, Query(min_length=1)],
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=20)] = 12,
    cursor: Annotated[datetime | None, Query()] = None,
) -> SearchTagResponse:
    return search_service.search_published_videos_by_tag(
        db, tag, limit=limit, cursor=cursor
    )


@router.get("/videos-by-tag", response_model=list[VideoResponse])
def videos_by_tag(
    tag: Annotated[str, Query(min_length=1)],
    db: DbSession,
):
    return search_service.search_videos_by_tag(db, tag)


@router.get("/users", response_model=list[PublicUserResponse])
def users(
    q: Annotated[str, Query(min_length=1)],
    db: DbSession,
):
    return search_service.search_users(db, q)
