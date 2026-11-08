"""Kiểm thử bảo mật độc lập: Xác thực JWT & Rate-limiting / Chống spam lượt xem.

Bao gồm:
1. Bảo mật JWT (Chức năng 2):
   - Chữ ký bị can thiệp (Tampered Signature) -> 401.
   - Token hết hạn (Expired Token) -> 401.
   - Thiếu header Authorization -> 401.
   - Token rác / Sai định dạng (Malformed / Bad Scheme) -> 401.
2. Rate-Limiting & Chống Spam Lượt xem (Chức năng 3):
   - Gọi lặp lại từ cùng một IP/User trong vòng 5 phút (300s) bị cooldown (counted=False).
   - Kiểm thử đồng thời (Concurrency) chống Race Condition: nhiều luồng gửi đồng thời
     chỉ duy nhất 1 request được ghi nhận tăng view.
   - Khách vãng lai và các IP khác nhau được tính độc lập.
   - Hết thời gian cooldown (sau 300s) được ghi nhận lượt xem mới.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import time
from uuid import uuid4

import jwt
import pytest

from app.core.config import get_settings
from app.models import VideoStatus
from app.services import view_tracking_service


@pytest.fixture(autouse=True)
def clean_cooldown_cache():
    """Tự động dọn dẹp cache cooldown trước và sau mỗi test case."""
    view_tracking_service.clear_cooldown_cache()
    yield
    view_tracking_service.clear_cooldown_cache()


# ==============================================================================
# NHÓM 1: BẢO MẬT JWT (AUTHENTICATION & TOKEN INTEGRITY)
# ==============================================================================


def test_jwt_missing_authorization_header_returns_401(client):
    """Khi truy cập endpoint yêu cầu xác thực mà không truyền header Authorization -> 401."""
    response = client.get("/api/v1/profile")
    assert response.status_code == 401
    assert "Vui lòng đăng nhập" in response.json()["detail"]


def test_jwt_tampered_signature_returns_401(client, register):
    """Token bị can thiệp hoặc thay đổi phần signature -> 401."""
    headers = register("tampered@example.com")
    valid_token = headers["Authorization"].split(" ")[1]

    parts = valid_token.split(".")
    assert len(parts) == 3

    # Làm biến dạng phần signature (đổi các ký tự cuối)
    tampered_sig = (
        "X" * len(parts[2]) if parts[2] != "X" * len(parts[2]) else "Y" * len(parts[2])
    )
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    res = client.get(
        "/api/v1/profile", headers={"Authorization": f"Bearer {tampered_token}"}
    )
    assert res.status_code == 401
    assert "Token không hợp lệ" in res.json()["detail"]


def test_jwt_expired_token_returns_401(client, register):
    """Token đã hết hạn thời gian hiệu lực (expired exp claim) -> 401."""
    headers = register("expired@example.com")
    valid_token = headers["Authorization"].split(" ")[1]

    # Giải mã không verify signature để lấy payload
    unverified_payload = jwt.decode(
        valid_token, options={"verify_signature": False}
    )

    # Đặt thời điểm hết hạn lùi về quá khứ 10 phút
    settings = get_settings()
    unverified_payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=10)

    # Ký lại với secret key nhưng exp đã quá hạn
    expired_token = jwt.encode(
        unverified_payload, settings.secret_key, algorithm="HS256"
    )

    res = client.get(
        "/api/v1/profile", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert res.status_code == 401
    assert "Token không hợp lệ" in res.json()["detail"]


def test_jwt_malformed_token_and_invalid_scheme_returns_401(client):
    """Token sai định dạng cấu trúc hoặc sai scheme (không phải Bearer) -> 401."""
    # 1. Scheme không phải Bearer
    res_basic = client.get(
        "/api/v1/profile", headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert res_basic.status_code == 401

    # 2. Token chuỗi ngẫu nhiên không phải chuẩn JWT 3 phần
    res_garbage = client.get(
        "/api/v1/profile", headers={"Authorization": "Bearer not-a-real-token-payload"}
    )
    assert res_garbage.status_code == 401
    assert "Token không hợp lệ" in res_garbage.json()["detail"]

    # 3. Header Bearer rỗng
    res_empty = client.get("/api/v1/profile", headers={"Authorization": "Bearer "})
    assert res_empty.status_code == 401


# ==============================================================================
# NHÓM 2: RATE-LIMITING & CHỐNG SPAM LƯỢT XEM (VIDEO VIEW TRACKING)
# ==============================================================================


def test_video_view_cooldown_within_5_minutes_anonymous_ip(client, seed_video):
    """Cùng 1 IP gửi request lặp lại trong 5 phút (300s): lần đầu tăng view, lần sau bị cooldown."""
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"
    headers = {"X-Forwarded-For": "203.0.113.10"}

    # Lần 1: Thành công tính view
    res1 = client.post(url, headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["counted"] is True
    assert data1["view_count"] == 1

    # Lần 2 (trong 5 phút): Cooldown chặn lại, không tăng view
    res2 = client.post(url, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["counted"] is False
    assert data2["view_count"] == 1


def test_video_view_cooldown_authenticated_user(client, register, seed_video):
    """User đã đăng nhập (JWT): Cooldown theo User ID, không cho spam view trong 5 phút."""
    headers = register("viewer_auth@example.com")
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"

    # Lần 1: Được ghi nhận
    res1 = client.post(url, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["counted"] is True
    assert res1.json()["view_count"] == 1

    # Lần 2 (ngay sau đó): Bị chặn cooldown
    res2 = client.post(url, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["counted"] is False
    assert res2.json()["view_count"] == 1


def test_video_view_different_actors_independent(client, register, seed_video):
    """Các IP khác nhau hoặc tài khoản khác nhau được ghi nhận lượt xem độc lập."""
    user1_headers = register("viewer_a@example.com")
    user2_headers = register("viewer_b@example.com")
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"

    # Actor 1 xem
    r1 = client.post(url, headers=user1_headers)
    assert r1.json()["counted"] is True
    assert r1.json()["view_count"] == 1

    # Actor 2 xem
    r2 = client.post(url, headers=user2_headers)
    assert r2.json()["counted"] is True
    assert r2.json()["view_count"] == 2

    # IP khác xem vãng lai
    r3 = client.post(url, headers={"X-Forwarded-For": "198.51.100.55"})
    assert r3.json()["counted"] is True
    assert r3.json()["view_count"] == 3

    # Actor 1 xem lại -> Bị cooldown chặn
    r1_repeat = client.post(url, headers=user1_headers)
    assert r1_repeat.json()["counted"] is False
    assert r1_repeat.json()["view_count"] == 3


def test_video_view_concurrency_race_condition(client, seed_video):
    """
    Kiểm thử đồng thời (Race Condition): 10 request từ cùng 1 nguồn gửi cùng lúc.
    Kỳ vọng:
    - 100% request trả về HTTP 200.
    - DUY NHẤT 1 request có counted = True và view_count = 1.
    - 9 request còn lại có counted = False.
    - Không xảy ra tình trạng view_count nhảy sai lệch.
    """
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"
    shared_headers = {"X-Forwarded-For": "192.0.2.77"}

    def send_view():
        return client.post(url, headers=shared_headers)

    num_threads = 10
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(send_view) for _ in range(num_threads)]
        results = [f.result() for f in futures]

    assert len(results) == num_threads
    for r in results:
        assert r.status_code == 200

    counted_true = [r for r in results if r.json()["counted"] is True]
    counted_false = [r for r in results if r.json()["counted"] is False]

    assert len(counted_true) == 1
    assert counted_true[0].json()["view_count"] == 1
    assert len(counted_false) == num_threads - 1

    # Xác nhận lượt xem cuối cùng trong database vẫn chuẩn xác là 1
    verify = client.post(url, headers=shared_headers)
    assert verify.json()["counted"] is False
    assert verify.json()["view_count"] == 1


def test_video_view_cooldown_expires_after_5_minutes(
    client, seed_video, monkeypatch
):
    """Sau thời gian cooldown 5 phút (300 giây), lượt xem tiếp theo được ghi nhận tăng view."""
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"
    headers = {"X-Forwarded-For": "198.51.100.99"}

    current_time = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: current_time)

    # Lần 1: t=1000s -> counted = True
    r1 = client.post(url, headers=headers)
    assert r1.json()["counted"] is True
    assert r1.json()["view_count"] == 1

    # Lần 2: t=1250s (sau 250s < 300s) -> Bị cooldown chặn
    current_time = 1250.0
    r2 = client.post(url, headers=headers)
    assert r2.json()["counted"] is False
    assert r2.json()["view_count"] == 1

    # Lần 3: t=1305s (sau 305s > 300s) -> Cooldown đã hết, được tính view mới
    current_time = 1305.0
    r3 = client.post(url, headers=headers)
    assert r3.json()["counted"] is True
    assert r3.json()["view_count"] == 2
