from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse

from app.core.config import get_settings
from app.dependencies import CurrentUser, DbSession, OptionalUser
from app.models import Video
from app.schemas import (
    AIResultResponse,
    AppealCreate,
    AppealResponse,
    ConfirmLabelsRequest,
    FeedResponse,
    LabelResponse,
    ReplaceVideoLabelsRequest,
    ReportCreate,
    ReportResponse,
    SearchTagResponse,
    VideoLabelsResponse,
    VideoResponse,
    VideoUpdate,
    VideoViewResponse,
)
from app.services import (
    ai_service,
    moderation_service,
    search_service,
    video_label_service,
    video_service,
    view_tracking_service,
)

router = APIRouter(tags=["videos"])


@router.post("/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
def upload_video(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    user: CurrentUser,
    db: DbSession,
    caption: str | None = None,
) -> Video:
    # Đọc tối đa đúng ngưỡng cho phép để phát hiện file quá lớn mà không nạp cả file vào bộ nhớ.
    settings = get_settings()
    video = video_service.upload_video(
        db,
        owner=user,
        filename=file.filename or "",
        content_type=file.content_type,
        content=file.file.read(settings.max_upload_size_bytes + 1),
        caption=caption,
    )
    background_tasks.add_task(ai_service.run_video_analysis, video.id)
    return video


@router.get("/videos", response_model=list[VideoResponse])
def list_my_videos(user: CurrentUser, db: DbSession) -> list[Video]:
    return video_service.list_owned_videos(db, user)


@router.get("/feed", response_model=FeedResponse)
def feed(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
    cursor: Annotated[datetime | None, Query()] = None,
) -> FeedResponse:
    return video_service.list_published_feed(db, limit=limit, cursor=cursor)


@router.get("/videos/search", response_model=SearchTagResponse)
def search_videos(
    tag: Annotated[str, Query(min_length=1)],
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=20)] = 12,
    cursor: Annotated[datetime | None, Query()] = None,
) -> SearchTagResponse:
    return search_service.search_published_videos_by_tag(
        db, tag, limit=limit, cursor=cursor
    )


@router.get("/videos/{video_id}/ai", response_model=AIResultResponse)
def ai_result(video_id: UUID, user: CurrentUser, db: DbSession) -> AIResultResponse:
    return ai_service.get_ai_result(db, video_id, user)


@router.patch("/videos/{video_id}", response_model=VideoResponse)
def update_video(
    video_id: UUID,
    payload: VideoUpdate,
    user: CurrentUser,
    db: DbSession,
) -> Video:
    return video_service.update_video(db, video_id, user, payload)


@router.get("/videos/{video_id}/labels", response_model=list[LabelResponse])
def labels(
    video_id: UUID,
    user: OptionalUser,
    db: DbSession,
) -> list[LabelResponse]:
    return video_label_service.list_video_labels(db, video_id, user)


@router.patch("/videos/{video_id}/labels", response_model=list[LabelResponse])
def replace_labels(
    video_id: UUID,
    payload: ReplaceVideoLabelsRequest,
    user: CurrentUser,
    db: DbSession,
) -> list[LabelResponse]:
    return video_label_service.replace_video_labels(db, video_id, user, payload)


@router.post(
    "/videos/{video_id}/labels/confirm",
    response_model=VideoLabelsResponse,
)
def confirm_labels(
    video_id: UUID,
    payload: ConfirmLabelsRequest,
    user: CurrentUser,
    db: DbSession,
) -> VideoLabelsResponse:
    return video_label_service.confirm_video_labels(db, video_id, user, payload)


@router.post(
    "/videos/{video_id}/appeals",
    response_model=AppealResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_appeal(
    video_id: UUID,
    payload: AppealCreate,
    user: CurrentUser,
    db: DbSession,
) -> AppealResponse:
    return moderation_service.create_appeal(db, video_id, user, payload.reason)


@router.get("/videos/{video_id}/stream", response_model=None)
def stream_video(
    video_id: UUID,
    user: OptionalUser,
    db: DbSession,
) -> FileResponse | RedirectResponse:
    target = video_service.resolve_stream_target(db, video_id, user)
    if isinstance(target, str):
        return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    return FileResponse(
        target,
        media_type="video/mp4",
        filename=target.name,
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.get("/videos/{video_id}/thumbnail", response_model=None)
def video_thumbnail(
    video_id: UUID,
    user: OptionalUser,
    db: DbSession,
) -> FileResponse | RedirectResponse:
    target = video_service.resolve_video_thumbnail(db, video_id, user)
    if isinstance(target, str):
        return RedirectResponse(target)
    return FileResponse(
        target,
        media_type=f"image/{target.suffix.lstrip('.')}",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: UUID, user: CurrentUser, db: DbSession) -> None:
    video_service.soft_delete_video(db, video_id, user)


@router.post("/videos/{video_id}/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    video_id: UUID,
    payload: ReportCreate,
    user: CurrentUser,
    db: DbSession,
) -> ReportResponse:
    return moderation_service.create_report(db, video_id, user, payload.reason)


@router.post(
    "/videos/{video_id}/views",
    response_model=VideoViewResponse,
    status_code=status.HTTP_200_OK,
)
def record_video_view(
    video_id: UUID,
    request: Request,
    user: OptionalUser,
    db: DbSession,
) -> VideoViewResponse:
    cf_ip = request.headers.get("CF-Connecting-IP")
    real_ip = request.headers.get("X-Real-IP")
    forwarded = request.headers.get("X-Forwarded-For")
    if cf_ip:
        client_ip = cf_ip.strip()
    elif real_ip:
        client_ip = real_ip.strip()
    elif forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"

    user_id = user.id if user is not None else None
    result = view_tracking_service.record_video_view(
        db,
        video_id=video_id,
        user_id=user_id,
        client_ip=client_ip,
    )
    return VideoViewResponse(**result)
