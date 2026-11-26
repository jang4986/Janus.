from app.models import UserRole, VideoStatus


def test_search_and_social_annotated_query_and_dependency_contracts(
    client, register, seed_video
):
    seeded = seed_video(status=VideoStatus.published, caption="annotated test")
    user_headers = register("social-annotated@example.com")

    # Missing required Query(...) parameters must still return 422.
    assert client.get("/api/v1/search/videos-by-tag").status_code == 422
    assert client.get("/api/v1/search/videos-by-tag/grid").status_code == 422
    assert client.get("/api/v1/search/users").status_code == 422

    # Valid queries work through DbSession Annotated alias.
    grid_res = client.get("/api/v1/search/videos-by-tag/grid?tag=Safe&limit=5")
    assert grid_res.status_code == 200
    assert "items" in grid_res.json()

    users_res = client.get("/api/v1/search/users?q=social")
    assert users_res.status_code == 200
    assert any(item["display_name"] == "social-annotated" for item in users_res.json())

    # Out-of-bounds Query constraints still return 422.
    assert client.get("/api/v1/search/videos-by-tag/grid?tag=Safe&limit=0").status_code == 422
    assert client.get("/api/v1/users/me/bookmarks?page=0", headers=user_headers).status_code == 422

    # Authenticated social endpoints work with CurrentUser + DbSession.
    like_res = client.post(
        f"/api/v1/videos/{seeded.video_id}/like",
        headers=user_headers,
    )
    assert like_res.status_code == 200
    assert like_res.json()["is_liked"] is True

    bookmark_res = client.post(
        f"/api/v1/videos/{seeded.video_id}/bookmark",
        headers=user_headers,
    )
    assert bookmark_res.status_code == 200
    assert bookmark_res.json()["is_bookmarked"] is True

    bookmarks_list = client.get("/api/v1/users/me/bookmarks", headers=user_headers)
    assert bookmarks_list.status_code == 200
    assert bookmarks_list.json()["total"] == 1


def test_users_and_admin_annotated_dependencies_and_bounds(client, register):
    user_headers = register("plain-annotated@example.com")
    admin_headers = register("admin-annotated@example.com", role=UserRole.admin)

    # AdminUser rejects non-admin and allows admin.
    assert client.get("/api/v1/admin/users", headers=user_headers).status_code == 403
    admin_res = client.get("/api/v1/admin/users?skip=0&limit=10", headers=admin_headers)
    assert admin_res.status_code == 200
    assert len(admin_res.json()) >= 2

    # Query bounds on admin stats still enforced.
    assert client.get("/api/v1/admin/stats?days=0", headers=admin_headers).status_code == 422

    # UploadFile Annotated[UploadFile, File()] still works on /profile/avatar.
    avatar_res = client.post(
        "/api/v1/profile/avatar",
        headers=user_headers,
        files={"file": ("avatar.png", b"\x89PNG\r\n\x1a\nfake-png", "image/png")},
    )
    assert avatar_res.status_code == 200
    assert avatar_res.json()["avatar_url"].startswith("/api/v1/profile/avatar/")

    # ModeratorUser rejects plain user and allows moderator.
    mod_headers = register("mod-annotated@example.com", role=UserRole.moderator)
    assert client.get("/api/v1/moderation/queue", headers=user_headers).status_code == 403
    assert client.get("/api/v1/moderation/queue", headers=mod_headers).status_code == 200

    # Annotated[LogoutRequest | None, Body()] = None works with empty body.
    assert client.post("/api/v1/auth/logout", headers=user_headers).status_code == 204
    assert client.get("/api/v1/profile", headers=user_headers).status_code == 401
