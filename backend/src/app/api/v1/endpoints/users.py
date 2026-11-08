from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.dependencies import current_user
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    MessageResponse,
    ProfileUpdate,
    UserResponse,
)
from app.services import profile_service
from app.services.storage_service import get_storage_service

router = APIRouter(tags=["users"])


@router.get("/profile", response_model=UserResponse)
def profile(user: User = Depends(current_user)) -> User:  # noqa: B008
    return user


@router.get("/profile/avatar/{user_id}")
def get_avatar(user_id: str):
    """Trả về ảnh đại diện của người dùng (local storage)."""
    settings = get_settings()
    if settings.storage_driver.strip().lower() == "s3":
        return None
    avatars_dir = Path(settings.local_storage_root) / "avatars" / str(user_id)
    if not avatars_dir.is_dir():
        return None
    for file_path in avatars_dir.iterdir():
        if file_path.is_file():
            return FileResponse(file_path)
    return None


@router.patch("/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> User:
    return profile_service.update_profile(db, user, payload)


@router.post(
    "/profile/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> MessageResponse:
    profile_service.change_password(db, user, payload)
    return MessageResponse(message="Đổi mật khẩu thành công")


@router.post("/profile/avatar", response_model=UserResponse)
def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(current_user),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> User:
    file_content = file.file.read()
    updated_user = profile_service.update_avatar(
        db,
        user,
        file_content=file_content,
        filename=file.filename or "avatar",
        content_type=file.content_type or "application/octet-stream",
    )
    return updated_user
