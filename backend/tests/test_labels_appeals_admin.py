"""Test nhãn (UC007/UC015), appeal (UC011/UC017) và admin (2.2.12/13, UC019/UC020)."""

from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Label, UserRole, VideoStatus


def ensure_label(name: str, active: bool = True) -> UUID:
    with SessionLocal() as db:
        label = db.scalar(select(Label).where(Label.name == name))
        if label is None:
            label = Label(name=name, is_active=active)
            db.add(label)
        else:
            label.is_active = active
        db.commit()
        return label.id


def attach_label(video_id: UUID, name: str, confidence: float = 0.9) -> None:
    from app.models import VideoLabel
    from app.services.ai_service import confidence_level

    ensure_label(name)
    with SessionLocal() as db:
        label = db.scalar(select(Label).where(Label.name == name))
        db.add(
            VideoLabel(
                video_id=video_id,
                label_id=label.id,
                confidence=confidence,
                level=confidence_level(confidence),
            )
        )
        db.commit()


def test_owner_confirms_labels(client, login, seed_video):
    ensure_label("Adult")
    video = seed_video()
    headers = login(video.email)

    response = client.post(
        f"/api/v1/videos/{video.video_id}/labels/confirm",
        json={"labels": ["Adult"]},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["labels"][0]["name"] == "Adult"
    assert response.json()["labels"][0]["level"] == "LOW"

    # Người khác không xác nhận được nhãn của video này.
    other = login(seed_video().email)
    assert (
        client.post(
            f"/api/v1/videos/{video.video_id}/labels/confirm",
            json={"labels": ["Adult"]},
            headers=other,
        ).status_code
        == 403
    )


def test_confirm_labels_validates_names(client, login, seed_video):
    video = seed_video()
    headers = login(video.email)
    url = f"/api/v1/videos/{video.video_id}/labels/confirm"

    unknown = client.post(url, json={"labels": ["ChuaTonTai"]}, headers=headers)
    assert unknown.status_code == 200
    assert unknown.json()["labels"][0]["name"] == "ChuaTonTai"

    ensure_label("Safe")
    ensure_label("Gore", active=False)
    inactive = client.post(url, json={"labels": ["Gore"]}, headers=headers)
    assert inactive.status_code == 200
    assert inactive.json()["labels"][0]["name"] == "Gore"

    ensure_label("Safe", active=True)
    duplicate = client.post(
        url,
        json={
            "labels": ["Safe", "safe"]
        },
        headers=headers,
    )
    assert duplicate.status_code == 200
    assert [label["name"] for label in duplicate.json()["labels"]] == ["Safe"]


def test_moderator_replaces_labels_and_owner_cannot(client, register, login, seed_video):
    ensure_label("Adult")
    ensure_label("Safe")
    video = seed_video()
    attach_label(video.video_id, "Safe")

    owner = login(video.email)
    assert (
        client.patch(
            f"/api/v1/videos/{video.video_id}/labels",
            json={"labels": [{"name": "Adult", "confidence": 0.9}]},
            headers=owner,
        ).status_code
        == 403
    )

    moderator = register("label-mod@example.com", role=UserRole.moderator)
    response = client.patch(
        f"/api/v1/videos/{video.video_id}/labels",
        json={"labels": [{"name": "Adult", "confidence": 0.9}]},
        headers=moderator,
    )
    assert response.status_code == 200
    # Nhãn cũ bị thay thế toàn bộ (multi-label nhưng không còn Safe).
    assert [label["name"] for label in response.json()] == ["Adult"]
    assert response.json()[0]["confidence"] == 0.9


def test_admin_label_crud(client, register):
    admin = register("label-admin@example.com", role=UserRole.admin)

    created = client.post("/api/v1/admin/labels", json={"name": "Violence"}, headers=admin)
    assert created.status_code == 201
    assert created.json()["video_count"] == 0

    duplicate = client.post("/api/v1/admin/labels", json={"name": "violence"}, headers=admin)
    assert duplicate.status_code == 409

    listed = client.get("/api/v1/admin/labels", headers=admin)
    assert listed.status_code == 200
    assert {item["name"] for item in listed.json()} == {"Violence"}

    label_id = created.json()["id"]
    deactivated = client.patch(
        f"/api/v1/admin/labels/{label_id}", json={"is_active": False}, headers=admin
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    renamed = client.patch(
        f"/api/v1/admin/labels/{label_id}", json={"name": "Gore"}, headers=admin
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Gore"

    empty_patch = client.patch(f"/api/v1/admin/labels/{label_id}", json={}, headers=admin)
    assert empty_patch.status_code == 422

    missing = client.patch(
        "/api/v1/admin/labels/00000000-0000-0000-0000-000000000000",
        json={"name": "Khac"},
        headers=admin,
    )
    assert missing.status_code == 404

    plain_user = register("plain-label-user@example.com")
    assert client.get("/api/v1/admin/labels", headers=plain_user).status_code == 403


def test_admin_updates_video_status_with_soft_delete(client, register, seed_video):
    admin = register("video-admin@example.com", role=UserRole.admin)
    video = seed_video(status=VideoStatus.published)
    url = f"/api/v1/admin/videos/{video.video_id}/status"

    rejected = client.patch(url, json={"status": "rejected", "reason": "vi phạm"}, headers=admin)
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    deleted = client.patch(url, json={"status": "deleted"}, headers=admin)
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert client.get("/api/v1/feed").json()["items"] == []
    # Đã xóa mềm thì không thấy nữa.
    assert client.patch(url, json={"status": "published"}, headers=admin).status_code == 404

    assert (
        client.patch(
            "/api/v1/admin/videos/00000000-0000-0000-0000-000000000000/status",
            json={"status": "published"},
            headers=admin,
        ).status_code
        == 404
    )
    other = seed_video(status=VideoStatus.published)
    assert (
        client.patch(
            f"/api/v1/admin/videos/{other.video_id}/status",
            json={"status": "processing"},
            headers=admin,
        ).status_code
        == 422
    )


def test_appeal_lifecycle(client, register, login, seed_video):
    admin = register("appeal-admin@example.com", role=UserRole.admin)
    moderator = register("appeal-mod@example.com", role=UserRole.moderator)
    video = seed_video(status=VideoStatus.rejected)
    owner = login(video.email)
    url = f"/api/v1/videos/{video.video_id}/appeals"

    # Video chưa bị từ chối thì không appeal được.
    published = seed_video(status=VideoStatus.published)
    assert (
        client.post(
            f"/api/v1/videos/{published.video_id}/appeals",
            json={"reason": "Tôi không đồng ý"},
            headers=login(published.email),
        ).status_code
        == 400
    )

    created = client.post(url, json={"reason": "Nội dung không vi phạm"}, headers=owner)
    assert created.status_code == 201
    assert created.json()["status"] == "open"
    appeal_id = created.json()["id"]

    # Không tạo trùng appeal đang mở.
    duplicate = client.post(url, json={"reason": "Xử lý lại đi"}, headers=owner)
    assert duplicate.status_code == 409

    # Người khác không appeal thay được (404 theo quyền sở hữu).
    assert (
        client.post(
            url, json={"reason": "Không liên quan"}, headers=login(seed_video().email)
        ).status_code
        == 404
    )

    # User thường không xem được danh sách appeal.
    assert client.get("/api/v1/moderation/appeals", headers=owner).status_code == 403

    assert client.get("/api/v1/moderation/appeals", headers=admin).status_code == 403

    queue = client.get("/api/v1/moderation/appeals", headers=moderator)
    assert queue.status_code == 200
    assert [item["id"] for item in queue.json()] == [appeal_id]
    assert queue.json()[0]["user_display_name"] == "Owner"

    decided = client.post(
        f"/api/v1/moderation/appeals/{appeal_id}/decision",
        json={"action": "approve", "reason": "Xem lại rồi, hợp lệ"},
        headers=moderator,
    )
    assert decided.status_code == 204

    # Video được đăng lại và appeal đã đóng.
    with SessionLocal() as db:
        from app.models import Video

        refreshed = db.get(Video, video.video_id)
        assert refreshed.status is VideoStatus.published
    assert client.get("/api/v1/moderation/appeals", headers=moderator).json() == []
    assert (
        client.post(
            f"/api/v1/moderation/appeals/{appeal_id}/decision",
            json={"action": "reject"},
            headers=moderator,
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/moderation/appeals/00000000-0000-0000-0000-000000000000/decision",
            json={"action": "reject"},
            headers=moderator,
        ).status_code
        == 404
    )


def test_appeal_rejected_keeps_video_hidden(client, register, login, seed_video):
    moderator = register("appeal-mod@example.com", role=UserRole.moderator)
    video = seed_video(status=VideoStatus.rejected)
    owner = login(video.email)
    created = client.post(
        f"/api/v1/videos/{video.video_id}/appeals",
        json={"reason": "Xin xem lại"},
        headers=owner,
    ).json()

    response = client.post(
        f"/api/v1/moderation/appeals/{created['id']}/decision",
        json={"action": "reject", "reason": "Vẫn vi phạm"},
        headers=moderator,
    )
    assert response.status_code == 204

    with SessionLocal() as db:
        from app.models import Video

        refreshed = db.get(Video, video.video_id)
        assert refreshed.status is VideoStatus.rejected


def test_moderator_and_system_stats(client, register):
    admin = register("stats-admin@example.com", role=UserRole.admin)
    plain = register("stats-user@example.com")

    assert client.get("/api/v1/admin/stats", headers=plain).status_code == 403

    stats = client.get("/api/v1/admin/stats?days=30", headers=admin)
    assert stats.status_code == 200
    body = stats.json()
    assert body["days"] == 30
    assert set(body["videos_by_status"]) == {item.value for item in VideoStatus}
    assert {"open", "resolved", "rejected"} <= set(body["reports_by_status"])
    assert {"open", "approved", "rejected"} <= set(body["appeals_by_status"])
    assert {"pending", "running", "succeeded", "failed"} <= set(body["jobs_by_status"])
    assert body["moderator_workload"] == []
    assert client.get("/api/v1/admin/stats?days=0", headers=admin).status_code == 422

    # UC019: thống kê theo moderator.
    moderator = register("stats-mod@example.com", role=UserRole.moderator)
    moderator_id = client.get("/api/v1/profile", headers=moderator).json()["id"]
    response = client.get(f"/api/v1/admin/moderators/{moderator_id}/stats", headers=admin)
    assert response.status_code == 200
    assert response.json()["videos_reviewed"] == 0
    assert response.json()["appeals_handled"] == 0
    assert response.json()["role"] == "moderator"

    assert (
        client.get(f"/api/v1/admin/moderators/{moderator_id}/stats", headers=plain).status_code
        == 403
    )
    plain_id = client.get("/api/v1/profile", headers=plain).json()["id"]
    not_moderator = client.get(f"/api/v1/admin/moderators/{plain_id}/stats", headers=admin)
    assert not_moderator.status_code == 400
    assert (
        client.get(
            "/api/v1/admin/moderators/00000000-0000-0000-0000-000000000000/stats",
            headers=admin,
        ).status_code
        == 404
    )


def test_moderation_queue_returns_enriched_dto(client, register, seed_video):
    moderator = register("queue-mod@example.com", role=UserRole.moderator)
    video = seed_video(status=VideoStatus.pending_review, caption="Video cần duyệt")
    attach_label(video.video_id, "Adult", confidence=0.73)

    resp = client.get("/api/v1/moderation/queue", headers=moderator)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    match = next(item for item in items if item["id"] == str(video.video_id))
    assert match["caption"] == "Video cần duyệt"
    assert "labels" in match
    assert any(label["name"] == "Adult" for label in match["labels"])
    assert "queue_reason" in match
    assert "Adult" in match["queue_reason"]
    assert "report_count" in match
    assert "thumbnail_url" in match


def test_moderation_decision_reject_requires_reason(client, register, seed_video):
    moderator = register("reject-val-mod@example.com", role=UserRole.moderator)
    video = seed_video(status=VideoStatus.pending_review)
    url = f"/api/v1/moderation/videos/{video.video_id}/decision"

    # Reject không có reason hoặc chuỗi rỗng -> 422
    resp_empty = client.post(url, json={"action": "reject", "reason": ""}, headers=moderator)
    assert resp_empty.status_code == 422
    assert "Lý do từ chối là bắt buộc" in resp_empty.text

    resp_none = client.post(url, json={"action": "reject"}, headers=moderator)
    assert resp_none.status_code == 422
    assert "Lý do từ chối là bắt buộc" in resp_none.text

    resp_whitespace = client.post(url, json={"action": "reject", "reason": "   "}, headers=moderator)
    assert resp_whitespace.status_code == 422


def test_moderation_decision_reject_and_approve_success(client, register, seed_video):
    moderator = register("decision-ok-mod@example.com", role=UserRole.moderator)
    video1 = seed_video(status=VideoStatus.pending_review)
    url1 = f"/api/v1/moderation/videos/{video1.video_id}/decision"

    # Reject với lý do hợp lệ -> thành công (204)
    resp_reject = client.post(
        url1,
        json={"action": "reject", "reason": "Vi phạm tiêu chuẩn cộng đồng về nội dung nhạy cảm"},
        headers=moderator,
    )
    assert resp_reject.status_code == 204

    with SessionLocal() as db:
        from app.models import ModerationReview, Video

        refreshed1 = db.get(Video, video1.video_id)
        assert refreshed1.status is VideoStatus.rejected
        review = db.scalar(select(ModerationReview).where(ModerationReview.video_id == video1.video_id))
        assert review is not None
        assert review.action.value == "reject"
        assert review.reason == "Vi phạm tiêu chuẩn cộng đồng về nội dung nhạy cảm"

    # Approve không bắt buộc reason -> thành công (204)
    video2 = seed_video(status=VideoStatus.pending_review)
    url2 = f"/api/v1/moderation/videos/{video2.video_id}/decision"
    resp_approve = client.post(url2, json={"action": "approve"}, headers=moderator)
    assert resp_approve.status_code == 204

    with SessionLocal() as db:
        from app.models import Video

        refreshed2 = db.get(Video, video2.video_id)
        assert refreshed2.status is VideoStatus.published


def test_admin_user_management_filters_and_banning(client, register):
    admin = register("superadmin@example.com", role=UserRole.admin)
    user1 = register("target-user1@example.com", role=UserRole.user)
    register("target-mod1@example.com", role=UserRole.moderator)
    plain = register("unauth-user@example.com", role=UserRole.user)

    # 1. Non-admin accessing admin users -> 403 Forbidden
    assert client.get("/api/v1/admin/users", headers=plain).status_code == 403

    # 2. Filter by role
    users_resp = client.get("/api/v1/admin/users?role=user", headers=admin)
    assert users_resp.status_code == 200
    assert all(u["role"] == "user" for u in users_resp.json())

    mods_resp = client.get("/api/v1/admin/users?role=moderator", headers=admin)
    assert mods_resp.status_code == 200
    assert any(u["email"] == "target-mod1@example.com" for u in mods_resp.json())

    # 3. Filter by search
    search_resp = client.get("/api/v1/admin/users?search=target-user1", headers=admin)
    assert search_resp.status_code == 200
    assert len(search_resp.json()) >= 1
    target_id = search_resp.json()[0]["id"]

    # 4. Ban user using status="banned"
    ban_resp = client.patch(
        f"/api/v1/admin/users/{target_id}/status",
        json={"status": "banned"},
        headers=admin,
    )
    assert ban_resp.status_code == 200
    assert ban_resp.json()["is_active"] is False

    # Target user token is now rejected
    assert client.get("/api/v1/profile", headers=user1).status_code == 401

    # Filter by is_active=false or status=banned
    banned_list = client.get("/api/v1/admin/users?status=banned", headers=admin)
    assert banned_list.status_code == 200
    assert any(u["id"] == target_id for u in banned_list.json())

    # 5. Unban user using status="active"
    unban_resp = client.patch(
        f"/api/v1/admin/users/{target_id}/status",
        json={"status": "active"},
        headers=admin,
    )
    assert unban_resp.status_code == 200
    assert unban_resp.json()["is_active"] is True

    # 6. Change role (Promote / Demote)
    promote_resp = client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        json={"role": "moderator"},
        headers=admin,
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["role"] == "moderator"


def test_admin_user_status_filter_contract(client, register):
    admin = register("status-filter-admin@example.com", role=UserRole.admin)
    active_user = register("status-active@example.com", role=UserRole.user)
    banned_user = register("status-banned@example.com", role=UserRole.user)

    # Khóa 1 user để có cả 2 trạng thái active/inactive.
    banned_id = client.get("/api/v1/profile", headers=banned_user).json()["id"]
    assert (
        client.patch(
            f"/api/v1/admin/users/{banned_id}/status",
            json={"status": "banned"},
            headers=admin,
        ).status_code
        == 200
    )
    active_id = client.get("/api/v1/profile", headers=active_user).json()["id"]

    # status=active -> chỉ user đang hoạt động.
    active_list = client.get("/api/v1/admin/users?status=active", headers=admin)
    assert active_list.status_code == 200
    active_ids = {u["id"] for u in active_list.json()}
    assert active_id in active_ids
    assert banned_id not in active_ids
    assert all(u["is_active"] for u in active_list.json())

    # status=banned -> chỉ user bị khóa.
    banned_list = client.get("/api/v1/admin/users?status=banned", headers=admin)
    assert banned_list.status_code == 200
    banned_ids = {u["id"] for u in banned_list.json()}
    assert banned_id in banned_ids
    assert active_id not in banned_ids
    assert all(not u["is_active"] for u in banned_list.json())

    # status=inactive (alias) -> tương đương banned.
    inactive_list = client.get("/api/v1/admin/users?status=inactive", headers=admin)
    assert inactive_list.status_code == 200
    assert banned_id in {u["id"] for u in inactive_list.json()}
    assert active_id not in {u["id"] for u in inactive_list.json()}

    # Không truyền status -> trả tất cả (all).
    all_list = client.get("/api/v1/admin/users?limit=100", headers=admin)
    assert all_list.status_code == 200
    all_ids = {u["id"] for u in all_list.json()}
    assert {active_id, banned_id} <= all_ids

    # is_active không còn là query param hợp lệ -> bị bỏ qua, không lọc.
    ignored = client.get("/api/v1/admin/users?is_active=false&limit=100", headers=admin)
    assert ignored.status_code == 200
    assert {active_id, banned_id} <= {u["id"] for u in ignored.json()}


def test_admin_audit_logs_and_permissions(client, register, seed_video):
    admin = register("audit-admin@example.com", role=UserRole.admin)
    mod = register("audit-mod@example.com", role=UserRole.moderator)
    plain = register("audit-user@example.com", role=UserRole.user)

    # 1. Non-admin cannot access audit logs (403)
    assert client.get("/api/v1/admin/audit-logs", headers=plain).status_code == 403
    assert client.get("/api/v1/admin/audit-logs", headers=mod).status_code == 403

    # 2. Moderator performs review action
    video = seed_video(status=VideoStatus.pending_review, caption="Video audit log test")
    url = f"/api/v1/moderation/videos/{video.video_id}/decision"
    client.post(
        url,
        json={"action": "reject", "reason": "Vi phạm tiêu chuẩn audit log"},
        headers=mod,
    )

    # 3. Admin queries audit logs
    resp = client.get("/api/v1/admin/audit-logs", headers=admin)
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    matched = next((l for l in logs if l["video_id"] == str(video.video_id)), None)
    assert matched is not None
    assert matched["action"] == "reject"
    assert matched["reason"] == "Vi phạm tiêu chuẩn audit log"
    assert matched["video_caption"] == "Video audit log test"
    assert matched["moderator_name"] is not None

    # 4. Filter by action
    reject_logs = client.get("/api/v1/admin/audit-logs?action=reject", headers=admin).json()
    assert all(l["action"] == "reject" for l in reject_logs)


def test_admin_stats_and_overview_summary(client, register, seed_video):
    admin = register("overview-admin@example.com", role=UserRole.admin)
    plain = register("overview-user@example.com", role=UserRole.user)

    # 1. Permission guard
    assert client.get("/api/v1/admin/overview", headers=plain).status_code == 403

    # 2. Overview / Stats returns enriched summary
    resp = client.get("/api/v1/admin/overview?days=30", headers=admin)
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    summary = data["summary"]
    assert summary["total_users"] >= 1
    assert "total_videos" in summary
    assert "published_videos" in summary
    assert "rejected_videos" in summary
    assert "pending_videos" in summary
    assert "pending_reports" in summary
    assert "open_appeals" in summary
    assert "ai_accuracy_rate" in summary
    assert summary["ai_accuracy_rate"] >= 0.0
