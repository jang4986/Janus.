from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies import CurrentUser, DbSession, bearer
from app.models import User
from app.schemas import (
    LoginRequest,
    LogoutRequest,
    PasswordForgotRequest,
    PasswordForgotResponse,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DbSession) -> User:
    return auth_service.create_user(db, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = auth_service.authenticate(db, payload)
    access_token, refresh_token = auth_service.create_session(db, user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: DbSession) -> TokenResponse:
    access_token, refresh_token = auth_service.refresh_session(db, payload.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    user: CurrentUser,
    db: DbSession,
    payload: Annotated[LogoutRequest | None, Body()] = None,
) -> None:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Vui lòng đăng nhập"
        )
    auth_service.logout(
        db,
        user=user,
        raw_access_token=credentials.credentials,
        raw_refresh_token=payload.refresh_token if payload else None,
    )


@router.post(
    "/password/forgot",
    response_model=PasswordForgotResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@router.post(
    "/forgot-password",
    response_model=PasswordForgotResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
def forgot_password(
    payload: PasswordForgotRequest,
    db: DbSession,
) -> PasswordForgotResponse:
    reset_token = auth_service.request_password_reset(db, payload.email)
    message = (
        "Yêu cầu đặt lại mật khẩu đã được tiếp nhận."
        if reset_token
        else "Nếu email tồn tại, hướng dẫn đặt lại mật khẩu đã được gửi."
    )
    return PasswordForgotResponse(message=message, reset_token=reset_token)


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
def reset_password(
    payload: PasswordResetRequest,
    db: DbSession,
) -> None:
    auth_service.reset_password(db, payload.token, payload.new_password)
