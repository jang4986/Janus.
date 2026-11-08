"""Nghiệp vụ profile, discriminator và đổi mật khẩu."""

import secrets
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.exceptions import ConflictError, InvalidInputError
from app.models import RefreshToken, User
from app.schemas import ChangePasswordRequest, ProfileUpdate
from app.services.storage_service import get_storage_service

MAX_DISCRIMINATOR = 9999
DISCRIMINATOR_RETRIES = 20


def allocate_discriminator(
    db: Session, display_name: str, preferred: str | None = None
) -> str:
    """Return an unused four-digit discriminator for a display name."""
    if preferred and not db.scalar(
        select(User.id).where(
            User.display_name == display_name,
            User.discriminator == preferred,
        )
    ):
        return preferred
    for _ in range(DISCRIMINATOR_RETRIES):
        candidate = f"{secrets.randbelow(MAX_DISCRIMINATOR) + 1:04d}"
        if not db.scalar(
            select(User.id).where(
                User.display_name == display_name,
                User.discriminator == candidate,
            )
        ):
            return candidate
    raise ConflictError("Không thể cấp mã định danh, vui lòng thử lại")


def update_profile(db: Session, user: User, payload: ProfileUpdate) -> User:
    values = payload.model_dump(exclude_unset=True)
    for _ in range(DISCRIMINATOR_RETRIES):
        current = db.get(User, user.id)
        if current is None:
            raise ConflictError("Tài khoản không còn tồn tại")
        if "display_name" in values and values["display_name"] != current.display_name:
            current.discriminator = allocate_discriminator(
                db, values["display_name"], preferred=current.discriminator
            )
            current.display_name = values["display_name"]
        if "bio" in values:
            current.bio = values["bio"]
        if "avatar_url" in values:
            current.avatar_url = (
                str(values["avatar_url"]) if values["avatar_url"] else None
            )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            db.refresh(current)
            return current
    raise ConflictError("Tên hiển thị đã xảy ra xung đột, vui lòng thử lại")


def change_password(
    db: Session, user: User, payload: ChangePasswordRequest
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise InvalidInputError("Mật khẩu hiện tại không chính xác")
    if verify_password(payload.new_password, user.password_hash):
        raise InvalidInputError("Mật khẩu mới không được trùng mật khẩu cũ")
    now = datetime.now(UTC)
    user.password_hash = hash_password(payload.new_password)
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()


def update_avatar(
    db: Session, user: User, file_content: bytes, filename: str, content_type: str
) -> User:
    """Tải lên avatar mới, lưu URL và cập nhật user.avatar_url."""
    storage = get_storage_service()
    settings = get_settings()
    file_key = f"avatars/{user.id}/{filename}"
    storage.upload_file(file_key, file_content, content_type)
    if settings.storage_driver.strip().lower() == "s3":
        user.avatar_url = storage.get_stream_url(file_key, public=True)
    else:
        user.avatar_url = f"/api/v1/profile/avatar/{user.id}"
    db.commit()
    db.refresh(user)
    return user
