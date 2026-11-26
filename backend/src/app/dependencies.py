from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import RevokedToken, User, UserRole

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Xác thực bắt buộc: thiếu hoặc sai token đều là 401."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập"
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
        jti = payload.get("jti")
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ"
        ) from exc

    if jti and db.get(RevokedToken, jti) is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã kết thúc. Vui lòng đăng nhập lại.",
        )

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không hợp lệ"
        )
    return user


def optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Xác thực tùy chọn cho endpoint công khai (feed, stream): ẩn danh vẫn gọi được."""
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
        jti = payload.get("jti")
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

    if jti and db.get(RevokedToken, jti) is not None:
        return None

    user = db.get(User, user_id)
    return user if user is not None and user.is_active else None


def require_roles(*roles: UserRole):
    def dependency(user: Annotated[User, Depends(current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thực hiện thao tác này",
            )
        return user

    return dependency


DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]
OptionalUser = Annotated[User | None, Depends(optional_user)]
AdminUser = Annotated[User, Depends(require_roles(UserRole.admin))]
ModeratorUser = Annotated[User, Depends(require_roles(UserRole.moderator))]
