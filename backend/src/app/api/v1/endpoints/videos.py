from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.dependencies import current_user, optional_user
from app.models import User, Video
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
from app.services.storage_service import get_storage_service
from app.services.thumbnail_service import extract_first_frame

router = APIRouter(tags=["videos"])


@router.post("/videos", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    caption: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
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
    if get_settings().ai_analysis_mode.strip().lower() == "off":
        background_tasks.add_task(ai_service.run_mock_analysis, video.id)
    else:
        background_tasks.add_task(ai_service.run_video_analysis, video.id)
    return video


@router.get("/videos", response_model=list[VideoResponse])
def list_my_videos(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Video]:
    return video_service.list_owned_videos(db, user)


@router.get("/feed", response_model=FeedResponse)
def feed(
    limit: int = Query(default=8, ge=1, le=20),
    cursor: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FeedResponse:
    return video_service.list_published_feed(db, limit=limit, cursor=cursor)


@router.get("/videos/search", response_model=SearchTagResponse)
def search_videos(
    tag: str = Query(..., min_length=1),
    limit: int = Query(default=12, ge=1, le=20),
    cursor: datetime | None = Query(default=None),  # noqa: B008
    db: Session = Depends(get_db),
) -> SearchTagResponse:
    return search_service.search_published_videos_by_tag(
        db, tag, limit=limit, cursor=cursor
    )


@router.get("/videos/{video_id}/ai", response_model=AIResultResponse)
def ai_result(video_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> AIResultResponse:
    return video_service.get_ai_result(db, video_id, user)


@router.patch("/videos/{video_id}", response_model=VideoResponse)
def update_video(
    video_id: UUID,
    payload: VideoUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Video:
    return video_service.update_video(db, video_id, user, payload)


@router.get("/videos/{video_id}/labels", response_model=list[LabelResponse])
def labels(
    video_id: UUID,
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> list[LabelResponse]:
    return video_label_service.list_video_labels(db, video_id, user)


@router.patch("/videos/{video_id}/labels", response_model=list[LabelResponse])
def replace_labels(
    video_id: UUID,
    payload: ReplaceVideoLabelsRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[LabelResponse]:
    return video_label_service.replace_video_labels(db, video_id, user, payload)


@router.post(
    "/videos/{video_id}/labels/confirm",
    response_model=VideoLabelsResponse,
)
def confirm_labels(
    video_id: UUID,
    payload: ConfirmLabelsRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
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
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AppealResponse:
    return moderation_service.create_appeal(db, video_id, user, payload.reason)


@router.get("/videos/{video_id}/stream", response_model=None)
def stream_video(
    video_id: UUID,
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
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
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> FileResponse | RedirectResponse:
    video = db.get(Video, video_id)
    if video is None or video.is_deleted:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh bìa")
    video_status = getattr(video.status, "value", video.status)
    video_visibility = getattr(video.visibility, "value", video.visibility)
    is_public = video_status == "published" and video_visibility == "public"
    is_owner = user is not None and video.owner_id == user.id
    user_role = getattr(user.role, "value", user.role) if user is not None else None
    is_staff = user_role in {"moderator", "admin"}
    if not (is_public or is_owner or is_staff):
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh bìa")
    storage = get_storage_service()
    if storage.is_s3:
        thumbnail_key = f"thumbnails/first-frame/{video_id}.jpg"
        thumbnail_url = storage.get_thumbnail_url(thumbnail_key)
        if thumbnail_url.startswith("/api/v1/videos/"):
            try:
                with storage.download_to_temp(video.storage_path) as video_path:
                    thumbnail = extract_first_frame(video_path)
                storage.upload_thumbnail(thumbnail_key, thumbnail)
                thumbnail_url = storage.get_thumbnail_url(thumbnail_key)
            except Exception as exc:
                raise HTTPException(status_code=404, detail="Không thể tạo ảnh xem trước cho video này") from exc
        return RedirectResponse(thumbnail_url)
    path = Path(get_settings().upload_dir) / f"thumbnails/first-frame/{video_id}.jpg"
    if not path.is_file():
        try:
            with storage.download_to_temp(video.storage_path) as video_path:
                thumbnail = extract_first_frame(video_path)
            storage.upload_thumbnail(f"thumbnails/first-frame/{video_id}.jpg", thumbnail)
        except Exception as exc:
            raise HTTPException(
                status_code=404,
                detail="Không thể tạo ảnh xem trước cho video này",
            ) from exc
    return FileResponse(
        path,
        media_type=f"image/{path.suffix.lstrip('.')}",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(video_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> None:
    video_service.soft_delete_video(db, video_id, user)


@router.post("/videos/{video_id}/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    video_id: UUID,
    payload: ReportCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
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
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
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
