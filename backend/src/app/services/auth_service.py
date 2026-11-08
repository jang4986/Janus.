"""Nghiệp vụ tài khoản: đăng ký, xác thực, phiên đăng nhập và khôi phục mật khẩu."""

from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_opaque_token,
    hash_password,
    new_opaque_token,
    verify_password,
)
from app.exceptions import ConflictError, InvalidInputError, UnauthorizedError
from app.models import PasswordResetToken, RefreshToken, RevokedToken, User
from app.schemas import LoginRequest, UserCreate
from app.services.profile_service import allocate_discriminator


def _is_expired(dt: datetime) -> bool:
    """Kiểm tra thời điểm đã quá hạn hay chưa, hỗ trợ cả offset-naive (SQLite) và aware (Postgres)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt <= datetime.now(UTC)


def create_user(db: Session, payload: UserCreate) -> User:
    """Tạo người dùng mới; email đã tồn tại là xung đột nghiệp vụ (409)."""
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise ConflictError("Email đã được sử dụng")
    for _ in range(5):
        user = User(
            email=email,
            display_name=payload.display_name,
            discriminator=allocate_discriminator(db, payload.display_name),
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if db.scalar(select(User).where(User.email == email)):
                raise ConflictError("Email đã được sử dụng") from None
        else:
            db.refresh(user)
            return user
    raise ConflictError("Không thể cấp mã định danh, vui lòng thử lại")


def authenticate(db: Session, payload: LoginRequest) -> User:
    """Xác thực bằng email + mật khẩu; sai thông tin là 401."""
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Tài khoản hoặc mật khẩu không chính xác")
    return user


def create_session(db: Session, user: User) -> tuple[str, str]:
    """Tạo access token và refresh token cho phiên đăng nhập mới."""
    access_token = create_access_token(user)
    raw_refresh = new_opaque_token()
    refresh_hash = hash_opaque_token(raw_refresh)
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
        )
    )
    db.commit()
    return access_token, raw_refresh


def refresh_session(db: Session, raw_token: str) -> tuple[str, str]:
    """Xoay vòng refresh token: cấp cặp token mới và thu hồi token cũ (401 nếu dùng lại/hết hạn)."""
    token_hash = hash_opaque_token(raw_token)
    token_record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    now = datetime.now(UTC)
    if token_record is None or token_record.revoked_at is not None or _is_expired(token_record.expires_at):
        raise UnauthorizedError("Refresh token không hợp lệ hoặc đã hết hạn")

    user = db.get(User, token_record.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Tài khoản không hợp lệ hoặc đã bị khóa")

    # Thu hồi refresh token cũ (token rotation)
    token_record.revoked_at = now

    # Cấp cặp token mới
    new_access = create_access_token(user)
    new_raw_refresh = new_opaque_token()
    new_refresh_hash = hash_opaque_token(new_raw_refresh)
    settings = get_settings()
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=new_refresh_hash,
            expires_at=expires_at,
        )
    )
    db.commit()
    return new_access, new_raw_refresh


def logout(
    db: Session,
    user: User,
    raw_access_token: str,
    raw_refresh_token: str | None = None,
) -> None:
    """Đăng xuất: đưa JTI của access token vào blacklist và thu hồi refresh token (nếu có)."""
    now = datetime.now(UTC)
    try:
        payload = decode_access_token(raw_access_token)
        jti = payload.get("jti")
        exp_ts = payload.get("exp")
        if jti and exp_ts:
            expires_at = datetime.fromtimestamp(exp_ts, tz=UTC)
            if db.get(RevokedToken, jti) is None:
                db.add(RevokedToken(jti=jti, user_id=user.id, expires_at=expires_at))
    except (jwt.PyJWTError, ValueError):
        pass

    if raw_refresh_token:
        refresh_hash = hash_opaque_token(raw_refresh_token)
        token_record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == refresh_hash))
        if token_record and token_record.revoked_at is None:
            token_record.revoked_at = now

    db.commit()


def request_password_reset(db: Session, email: str) -> str | None:
    """Yêu cầu đặt lại mật khẩu: sinh token nếu email tồn tại (generic response chống dò user)."""
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not user.is_active:
        return None

    raw_token = new_opaque_token()
    token_hash = hash_opaque_token(raw_token)
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.password_reset_expire_minutes)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
    )
    db.commit()
    return raw_token


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    """Đặt lại mật khẩu: kiểm tra token (chỉ dùng 1 lần) và thu hồi toàn bộ phiên đăng nhập cũ."""
    token_hash = hash_opaque_token(raw_token)
    reset_record = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    now = datetime.now(UTC)
    if reset_record is None or reset_record.used_at is not None or _is_expired(reset_record.expires_at):
        raise InvalidInputError("Token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn")

    user = db.get(User, reset_record.user_id)
    if user is None or not user.is_active:
        raise InvalidInputError("Tài khoản không hợp lệ hoặc đã bị khóa")

    # Đánh dấu token đã sử dụng
    reset_record.used_at = now
    # Đổi mật khẩu
    user.password_hash = hash_password(new_password)
    # Thu hồi toàn bộ refresh token hiện có của user
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
