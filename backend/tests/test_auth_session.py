"""Test phiên đăng nhập, refresh token, khôi phục mật khẩu và hồ sơ."""


def test_logout_revokes_current_access_token(client, register):
    headers = register("logout@example.com")
    assert client.get("/api/v1/profile", headers=headers).status_code == 200

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204

    after = client.get("/api/v1/profile", headers=headers)
    assert after.status_code == 401
    assert "Phiên đăng nhập đã kết thúc" in after.json()["detail"]


def test_login_returns_refresh_token_and_rotation(client, register):
    email = "refresh@example.com"
    register(email)
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).json()
    first_refresh = login["refresh_token"]
    assert first_refresh

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["refresh_token"] != first_refresh

    # Access token mới phải dùng được.
    profile = client.get(
        "/api/v1/profile",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert profile.status_code == 200

    # Refresh token đã dùng (xoay vòng) không được dùng lại.
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert reuse.status_code == 401


def test_logout_with_refresh_token_revokes_the_pair(client, register):
    email = "pair@example.com"
    headers = register(email)
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).json()

    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": login["refresh_token"]},
        headers=headers,
    )
    assert response.status_code == 204
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}).status_code
        == 401
    )


def test_invalid_refresh_token_is_rejected(client):
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-valid-token-value"}).status_code
        == 401
    )
    assert client.post("/api/v1/auth/refresh", json={}).status_code == 422


def test_password_reset_flow_revokes_existing_sessions(client, register):
    email = "reset@example.com"
    register(email)
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).json()
    old_refresh = login["refresh_token"]

    forgot = client.post("/api/v1/auth/password/forgot", json={"email": email})
    assert forgot.status_code == 202
    reset_token = forgot.json()["reset_token"]
    assert reset_token

    reset = client.post(
        "/api/v1/auth/password/reset",
        json={"token": reset_token, "new_password": "newpassword123"},
    )
    assert reset.status_code == 204

    # Mật khẩu cũ bị từ chối, mật khẩu mới hoạt động.
    assert (
        client.post("/api/v1/auth/login", json={"email": email, "password": "password123"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": email, "password": "newpassword123"}
        ).status_code
        == 200
    )
    # Phiên cũ bị thu hồi khi đổi mật khẩu.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401
    # Token đặt lại mật khẩu chỉ dùng một lần.
    assert (
        client.post(
            "/api/v1/auth/password/reset",
            json={"token": reset_token, "new_password": "anotherpass123"},
        ).status_code
        == 400
    )


def test_password_forgot_is_generic_for_unknown_email(client):
    response = client.post("/api/v1/auth/password/forgot", json={"email": "nobody@example.com"})
    assert response.status_code == 202
    assert response.json()["reset_token"] is None


def test_password_reset_rejects_bad_token(client):
    assert (
        client.post(
            "/api/v1/auth/password/reset",
            json={"token": "khong-phai-token-hop-le", "new_password": "newpassword123"},
        ).status_code
        == 400
    )


def test_legacy_password_alias_routes_are_removed(client):
    assert (
        client.post("/api/v1/auth/forgot-password", json={"email": "alias@example.com"}).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": "token-khong-ton-tai", "new_password": "newpassword123"},
        ).status_code
        == 404
    )


def test_profile_update_display_name(client, register):
    headers = register("profile@example.com")
    response = client.patch(
        "/api/v1/profile", json={"display_name": "Tên Mới"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Tên Mới"


def test_profile_password_change_requires_current_password(client, register, login):
    email = "password-change@example.com"
    headers = register(email)
    refresh_before = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    ).json()["refresh_token"]

    wrong = client.post(
        "/api/v1/profile/change-password",
        json={
            "current_password": "sai-mat-khau-nay",
            "new_password": "newpassword123",
            "confirm_new_password": "newpassword123",
        },
        headers=headers,
    )
    assert wrong.status_code == 400

    ok = client.post(
        "/api/v1/profile/change-password",
        json={
            "current_password": "password123",
            "new_password": "newpassword123",
            "confirm_new_password": "newpassword123",
        },
        headers=headers,
    )
    assert ok.status_code == 200
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": email, "password": "newpassword123"}
        ).status_code
        == 200
    )
    # Đổi mật khẩu thu hồi refresh token cũ.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_before}).status_code == 401


def test_profile_update_accepts_empty_payload(client, register):
    headers = register("empty-update@example.com")
    assert client.patch("/api/v1/profile", json={}, headers=headers).status_code == 200
    assert client.patch("/api/v1/profile", json={"display_name": "X"}).status_code == 401
