from pathlib import Path

from app.core.media import validate_mp4_content
from app.db.session import SessionLocal
from app.models import User, UserRole

TEST_STORAGE_PATH = Path(__file__).resolve().parents[1] / "test_storage"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_login_and_profile(client):
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "display_name": "User", "password": "password123"},
    )
    assert registered.status_code == 201

    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert logged_in.status_code == 200
    token = logged_in.json()["access_token"]

    profile = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["email"] == "user@example.com"


def test_auth_rejects_invalid_credentials_and_duplicate_registration(client):
    payload = {
        "email": "duplicate@example.com",
        "display_name": "Duplicate",
        "password": "password123",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201

    duplicate = client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409

    invalid_login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": "wrong-password"},
    )
    assert invalid_login.status_code == 401


def test_auth_rejects_invalid_input_and_tokens(client):
    short_password = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "display_name": "Short", "password": "short"},
    )
    assert short_password.status_code == 422

    missing_token = client.get("/api/v1/profile")
    assert missing_token.status_code == 401

    invalid_token = client.get(
        "/api/v1/profile",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert invalid_token.status_code == 401


def test_profile_returns_authenticated_user_contract(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "profile@example.com", "display_name": "Profile User", "password": "password123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "profile@example.com", "password": "password123"},
    ).json()["access_token"]

    response = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert {"id", "email", "display_name", "role"} <= set(response.json())
    assert response.json()["display_name"] == "Profile User"
    assert response.json()["role"] == "user"


def test_duplicate_report_is_rejected(client, real_video_path):
    client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "display_name": "User", "password": "password123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    ).json()["access_token"]

    response = client.post(
        "/api/v1/videos",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (real_video_path.name, real_video_path.read_bytes(), "video/mp4")},
    )
    assert response.status_code == 201
    video_id = response.json()["id"]

    first = client.post(
        f"/api/v1/videos/{video_id}/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Nội dung không phù hợp"},
    )
    second = client.post(
        f"/api/v1/videos/{video_id}/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Báo cáo trùng"},
    )
    assert first.status_code == 201
    assert client.get("/api/v1/feed").json()["items"] == []
    assert second.status_code == 409


def test_content_report_validates_auth_input_and_missing_video(client, real_video_path):
    client.post(
        "/api/v1/auth/register",
        json={"email": "reporter@example.com", "display_name": "Reporter", "password": "password123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "reporter@example.com", "password": "password123"},
    ).json()["access_token"]
    uploaded = client.post(
        "/api/v1/videos",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (real_video_path.name, real_video_path.read_bytes(), "video/mp4")},
    )
    video_id = uploaded.json()["id"]

    valid = client.post(
        f"/api/v1/videos/{video_id}/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Nội dung vi phạm chính sách"},
    )
    missing_auth = client.post(
        f"/api/v1/videos/{video_id}/reports",
        json={"reason": "Thiếu xác thực"},
    )
    short_reason = client.post(
        f"/api/v1/videos/{video_id}/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "x"},
    )
    missing_reason = client.post(
        f"/api/v1/videos/{video_id}/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    missing_video = client.post(
        "/api/v1/videos/00000000-0000-0000-0000-000000000000/reports",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Video không tồn tại"},
    )

    assert uploaded.status_code == 201
    assert valid.status_code == 201
    assert valid.json()["video_id"] == video_id
    assert valid.json()["status"] == "open"
    assert missing_auth.status_code == 401
    assert short_reason.status_code == 422
    assert missing_reason.status_code == 422
    assert missing_video.status_code == 404


def test_moderation_queue_reports_and_decisions(client, real_video_path):
    client.post(
        "/api/v1/auth/register",
        json={"email": "moderator@example.com", "display_name": "Moderator", "password": "password123"},
    )
    moderator_token = client.post(
        "/api/v1/auth/login",
        json={"email": "moderator@example.com", "password": "password123"},
    ).json()["access_token"]
    with SessionLocal() as db:
        moderator = db.query(User).filter(User.email == "moderator@example.com").one()
        moderator.role = UserRole.moderator
        db.commit()

    client.post(
        "/api/v1/auth/register",
        json={"email": "reporter-one@example.com", "display_name": "Reporter One", "password": "password123"},
    )
    reporter_one_token = client.post(
        "/api/v1/auth/login",
        json={"email": "reporter-one@example.com", "password": "password123"},
    ).json()["access_token"]
    client.post(
        "/api/v1/auth/register",
        json={"email": "reporter-two@example.com", "display_name": "Reporter Two", "password": "password123"},
    )
    reporter_two_token = client.post(
        "/api/v1/auth/login",
        json={"email": "reporter-two@example.com", "password": "password123"},
    ).json()["access_token"]

    video_ids = []
    for token in (reporter_one_token, reporter_two_token):
        uploaded = client.post(
            "/api/v1/videos",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": (real_video_path.name, real_video_path.read_bytes(), "video/mp4")},
        )
        assert uploaded.status_code == 201
        video_ids.append(uploaded.json()["id"])

    reports = []
    for video_id, token in zip(video_ids, (reporter_two_token, reporter_one_token)):
        report = client.post(
            f"/api/v1/videos/{video_id}/reports",
            headers={"Authorization": f"Bearer {token}"},
            json={"reason": "Requires moderation review"},
        )
        assert report.status_code == 201
        reports.append(report.json()["id"])

    regular_queue = client.get("/api/v1/moderation/queue", headers={"Authorization": f"Bearer {reporter_one_token}"})
    queue = client.get("/api/v1/moderation/queue", headers={"Authorization": f"Bearer {moderator_token}"})
    moderation_reports = client.get("/api/v1/moderation/reports", headers={"Authorization": f"Bearer {moderator_token}"})
    first_decision = client.post(
        f"/api/v1/moderation/reports/{reports[0]}/decision",
        headers={"Authorization": f"Bearer {moderator_token}"},
        json={"action": "approve", "reason": "Policy violation confirmed"},
    )
    second_decision = client.post(
        f"/api/v1/moderation/reports/{reports[1]}/decision",
        headers={"Authorization": f"Bearer {moderator_token}"},
        json={"action": "reject", "reason": "Report not substantiated"},
    )
    repeated_decision = client.post(
        f"/api/v1/moderation/reports/{reports[0]}/decision",
        headers={"Authorization": f"Bearer {moderator_token}"},
        json={"action": "approve"},
    )
    missing_decision = client.post(
        "/api/v1/moderation/reports/00000000-0000-0000-0000-000000000000/decision",
        headers={"Authorization": f"Bearer {moderator_token}"},
        json={"action": "approve"},
    )

    assert regular_queue.status_code == 403
    assert queue.status_code == 200
    assert {item["id"] for item in queue.json()} == set(video_ids)
    assert moderation_reports.status_code == 200
    assert {item["id"] for item in moderation_reports.json()} == set(reports)
    assert first_decision.status_code == 204
    assert second_decision.status_code == 204
    assert repeated_decision.status_code == 404
    assert missing_decision.status_code == 404


def test_admin_management_lists_searches_status_and_roles(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "display_name": "Admin", "password": "password123"},
    )
    admin_token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    ).json()["access_token"]
    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == "admin@example.com").one()
        admin.role = UserRole.admin
        db.commit()

    client.post(
        "/api/v1/auth/register",
        json={"email": "managed@example.com", "display_name": "Managed User", "password": "password123"},
    )
    managed = client.post(
        "/api/v1/auth/login",
        json={"email": "managed@example.com", "password": "password123"},
    )
    managed_token = managed.json()["access_token"]
    with SessionLocal() as db:
        managed_user = db.query(User).filter(User.email == "managed@example.com").one()
        managed_id = str(managed_user.id)

    headers = {"Authorization": f"Bearer {admin_token}"}
    user_list = client.get("/api/v1/admin/users", headers=headers)
    search = client.get("/api/v1/admin/users?search=Managed", headers=headers)
    detail = client.get(f"/api/v1/admin/users/{managed_id}", headers=headers)
    promote = client.patch(
        f"/api/v1/admin/users/{managed_id}/role",
        headers=headers,
        json={"role": "moderator"},
    )
    moderators = client.get("/api/v1/admin/moderators", headers=headers)
    deactivate = client.patch(
        f"/api/v1/admin/users/{managed_id}/status",
        headers=headers,
        json={"is_active": False},
    )
    regular_access = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {managed_token}"})
    missing = client.get(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )

    assert user_list.status_code == 200
    assert search.status_code == 200
    assert len(search.json()) == 1
    assert detail.status_code == 200
    assert detail.json()["email"] == "managed@example.com"
    assert promote.status_code == 200
    assert promote.json()["role"] == "moderator"
    assert moderators.status_code == 200
    assert any(item["id"] == managed_id for item in moderators.json())
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False
    assert regular_access.status_code == 401
    assert missing.status_code == 404


def test_video_upload_requires_auth_and_accepts_mp4(client, real_video_path):
    real_video = real_video_path.read_bytes()
    client.post(
        "/api/v1/auth/register",
        json={"email": "upload@example.com", "display_name": "Uploader", "password": "password123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "upload@example.com", "password": "password123"},
    ).json()["access_token"]

    missing_auth = client.post(
        "/api/v1/videos",
        files={"file": (real_video_path.name, real_video, "video/mp4")},
    )
    uploaded = client.post(
        "/api/v1/videos?caption=Upload%20test",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (real_video_path.name, real_video, "video/mp4")},
    )
    invalid_type = client.post(
        "/api/v1/videos",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sample.txt", b"fixture", "text/plain")},
    )
    missing_file = client.post(
        "/api/v1/videos",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert missing_auth.status_code == 401
    assert uploaded.status_code == 201
    assert uploaded.json()["original_filename"] == real_video_path.name
    assert uploaded.json()["caption"] == "Upload test"
    assert uploaded.json()["status"] == "processing"
    assert any(path.read_bytes() == real_video for path in TEST_STORAGE_PATH.glob("*.mp4"))
    assert invalid_type.status_code == 400
    assert missing_file.status_code == 422


def test_video_upload_rejects_invalid_mp4_content(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "invalid-video@example.com", "display_name": "Invalid Video", "password": "password123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "invalid-video@example.com", "password": "password123"},
    ).json()["access_token"]
    fake_mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2"

    response = client.post(
        "/api/v1/videos",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("fake.mp4", fake_mp4, "video/mp4")},
    )

    assert response.status_code == 400
    assert "codec" in response.json()["detail"].lower()


def test_real_video_fixture_has_valid_mp4_magic_bytes_and_codec(real_video_path):
    assert validate_mp4_content(real_video_path.read_bytes()) == "avc1"


def test_ai_analysis_returns_mock_result_and_enforces_video_ownership(client, real_video_path):
    client.post(
        "/api/v1/auth/register",
        json={"email": "ai-owner@example.com", "display_name": "AI Owner", "password": "password123"},
    )
    owner_token = client.post(
        "/api/v1/auth/login",
        json={"email": "ai-owner@example.com", "password": "password123"},
    ).json()["access_token"]
    client.post(
        "/api/v1/auth/register",
        json={"email": "ai-other@example.com", "display_name": "AI Other", "password": "password123"},
    )
    other_token = client.post(
        "/api/v1/auth/login",
        json={"email": "ai-other@example.com", "password": "password123"},
    ).json()["access_token"]
    uploaded = client.post(
        "/api/v1/videos",
        headers={"Authorization": f"Bearer {owner_token}"},
        files={"file": (real_video_path.name, real_video_path.read_bytes(), "video/mp4")},
    )
    video_id = uploaded.json()["id"]

    owner_result = client.get(
        f"/api/v1/videos/{video_id}/ai",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    other_result = client.get(
        f"/api/v1/videos/{video_id}/ai",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    missing_token = client.get(f"/api/v1/videos/{video_id}/ai")
    invalid_id = client.get(
        "/api/v1/videos/not-a-uuid/ai",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert owner_result.status_code == 200
    assert owner_result.json()["job_status"] == "succeeded"
    assert owner_result.json()["transcript"]
    labels = owner_result.json()["labels"]
    assert labels[0]["name"] == "Safe"
    assert 0 <= labels[0]["confidence"] <= 1
    assert labels[0]["level"] in {"LOW", "MEDIUM", "HIGH"}
    assert labels[0]["source"] == "ai"
    assert other_result.status_code == 404
    assert missing_token.status_code == 401
    assert invalid_id.status_code == 422


def test_video_management_lists_owned_videos_and_enforces_delete_ownership(client, real_video_path):
    client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "display_name": "Owner", "password": "password123"},
    )
    owner_token = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    ).json()["access_token"]
    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "display_name": "Other", "password": "password123"},
    )
    other_token = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "password123"},
    ).json()["access_token"]

    uploaded = client.post(
        "/api/v1/videos",
        headers={"Authorization": f"Bearer {owner_token}"},
        files={"file": (real_video_path.name, real_video_path.read_bytes(), "video/mp4")},
    )
    assert uploaded.status_code == 201, uploaded.text
    video_id = uploaded.json()["id"]

    owner_list = client.get("/api/v1/videos", headers={"Authorization": f"Bearer {owner_token}"})
    public_feed = client.get("/api/v1/feed")
    other_delete = client.delete(
        f"/api/v1/videos/{video_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    owner_delete = client.delete(
        f"/api/v1/videos/{video_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    after_delete = client.get("/api/v1/videos", headers={"Authorization": f"Bearer {owner_token}"})

    assert uploaded.status_code == 201
    assert any(item["id"] == video_id for item in owner_list.json())
    assert public_feed.status_code == 200
    assert isinstance(public_feed.json()["items"], list)
    assert other_delete.status_code == 404
    assert owner_delete.status_code == 204
    assert all(item["id"] != video_id for item in after_delete.json())


def test_video_stream_serves_published_video_and_hides_pending_one(client, real_video_path):
    client.post(
        "/api/v1/auth/register",
        json={"email": "stream@example.com", "display_name": "Streamer", "password": "password123"},
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"email": "stream@example.com", "password": "password123"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    uploaded = client.post(
        "/api/v1/videos",
        headers=headers,
        files={"file": (real_video_path.name, real_video_path.read_bytes(), "video/mp4")},
    )
    assert uploaded.status_code == 201, uploaded.text
    video_id = uploaded.json()["id"]

    # Video đã publish: ai cũng phát được mà không cần token.
    published = client.get(f"/api/v1/videos/{video_id}/stream")
    assert published.status_code == 200
    assert published.headers["content-type"].startswith("video/mp4")
    assert published.content == real_video_path.read_bytes()

    # Báo cáo chuyển video sang hàng đợi kiểm duyệt: ẩn danh không xem được, chủ video vẫn xem được.
    reported = client.post(
        f"/api/v1/videos/{video_id}/reports",
        headers=headers,
        json={"reason": "Nội dung cần xem xét"},
    )
    assert reported.status_code == 201
    assert client.get(f"/api/v1/videos/{video_id}/stream").status_code == 404
    assert client.get(f"/api/v1/videos/{video_id}/stream", headers=headers).status_code == 200

    missing = client.get("/api/v1/videos/00000000-0000-0000-0000-000000000000/stream")
    assert missing.status_code == 404
