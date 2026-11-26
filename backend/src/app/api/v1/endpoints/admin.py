from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.dependencies import AdminUser, DbSession
from app.models import User, UserRole, Video
from app.schemas import (
    AdminAuditLogItem,
    AdminRoleUpdate,
    AdminStatsResponse,
    AdminUserDetail,
    AdminUserStatusUpdate,
    AdminUserSummary,
    AdminVideoStatusUpdate,
    LabelAdminCreate,
    LabelAdminResponse,
    LabelAdminUpdate,
    ModeratorStatsResponse,
    VideoResponse,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserSummary])
def admin_list_users(
    user: AdminUser,
    db: DbSession,
    search: str | None = None,
    role: UserRole | None = None,
    status: str | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[User]:
    is_active: bool | None = None
    if status is not None:
        s = status.strip().lower()
        if s in {"active", "unbanned"}:
            is_active = True
        elif s in {"banned", "inactive", "blocked"}:
            is_active = False
    return admin_service.list_users(
        db=db,
        search=search,
        role=role,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@router.get("/audit-logs", response_model=list[AdminAuditLogItem])
def admin_list_audit_logs(
    user: AdminUser,
    db: DbSession,
    action: str | None = None,
    moderator_id: UUID | None = None,
    video_id: UUID | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict]:
    return admin_service.list_audit_logs(
        db=db,
        action=action,
        moderator_id=moderator_id,
        video_id=video_id,
        skip=skip,
        limit=limit,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def admin_get_user(
    user_id: UUID,
    user: AdminUser,
    db: DbSession,
) -> User:
    return admin_service.get_user(db, user_id)


@router.patch("/users/{user_id}/status", response_model=AdminUserDetail)
def admin_update_user_status(
    user_id: UUID,
    payload: AdminUserStatusUpdate,
    user: AdminUser,
    db: DbSession,
) -> User:
    return admin_service.update_user_status(db, user_id, user, payload.is_active)


@router.get("/moderators", response_model=list[AdminUserSummary])
def admin_list_moderators(
    user: AdminUser,
    db: DbSession,
) -> list[User]:
    return admin_service.list_moderators(db)


@router.patch("/users/{user_id}/role", response_model=AdminUserDetail)
def admin_update_user_role(
    user_id: UUID,
    payload: AdminRoleUpdate,
    user: AdminUser,
    db: DbSession,
) -> User:
    return admin_service.update_user_role(db, user_id, user, payload.role)


@router.post(
    "/labels",
    response_model=LabelAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_label(
    payload: LabelAdminCreate,
    user: AdminUser,
    db: DbSession,
) -> dict:
    return admin_service.create_label(db, payload.name)


@router.get("/labels", response_model=list[LabelAdminResponse])
def admin_list_labels(
    user: AdminUser,
    db: DbSession,
) -> list[dict]:
    return admin_service.list_labels(db)


@router.patch("/labels/{label_id}", response_model=LabelAdminResponse)
def admin_update_label(
    label_id: UUID,
    payload: LabelAdminUpdate,
    user: AdminUser,
    db: DbSession,
) -> dict:
    return admin_service.update_label(
        db, label_id, name=payload.name, is_active=payload.is_active
    )


@router.patch("/videos/{video_id}/status", response_model=VideoResponse)
def admin_update_video_status(
    video_id: UUID,
    payload: AdminVideoStatusUpdate,
    user: AdminUser,
    db: DbSession,
) -> Video:
    return admin_service.update_video_status(
        db, video_id, actor=user, status=payload.status, reason=payload.reason
    )


@router.get("/overview", response_model=AdminStatsResponse)
@router.get("/stats", response_model=AdminStatsResponse)
def admin_get_stats(
    user: AdminUser,
    db: DbSession,
    days: Annotated[int, Query(ge=1)] = 30,
) -> dict:
    return admin_service.get_system_stats(db, days)


@router.get("/moderators/{moderator_id}/stats", response_model=ModeratorStatsResponse)
def admin_get_moderator_stats(
    moderator_id: UUID,
    user: AdminUser,
    db: DbSession,
) -> dict:
    return admin_service.get_moderator_stats(db, moderator_id)
