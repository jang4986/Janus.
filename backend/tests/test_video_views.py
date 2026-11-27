import time
from uuid import uuid4

import pytest

from app.models import VideoStatus
from app.services import view_tracking_service


@pytest.fixture(autouse=True)
def clean_cooldown_cache():
    view_tracking_service.clear_cooldown_cache()
    yield
    view_tracking_service.clear_cooldown_cache()


def test_video_view_first_request_and_cooldown_within_5_minutes(client, seed_video):
    """
    Test request lần 1: counted = True, view_count tăng 1.
    Test request lần 2 trong vòng 5 phút: counted = False, view_count không đổi.
    """
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"

    # Request lần 1: Ghi nhận view thành công
    res1 = client.post(url)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["video_id"] == str(seeded.video_id)
    assert data1["counted"] is True
    assert data1["view_count"] == 1

    # Request lần 2: Đang trong cooldown 5 phút (300s) -> Không tăng view
    res2 = client.post(url)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["video_id"] == str(seeded.video_id)
    assert data2["counted"] is False
    assert data2["view_count"] == 1


def test_video_view_authenticated_user_cooldown(client, register, seed_video):
    """Xác minh cooldown hoạt động chính xác với tài khoản đã đăng nhập (User ID)."""
    headers = register("viewer@example.com")
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"

    # Lần 1 có JWT
    res1 = client.post(url, headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["counted"] is True
    assert data1["view_count"] == 1

    # Lần 2 có cùng JWT trong thời gian cooldown
    res2 = client.post(url, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["counted"] is False
    assert data2["view_count"] == 1


def test_video_view_different_actors_increment_independently(
    client, register, seed_video
):
    """Người dùng khác nhau hoặc IP khác nhau được tính view độc lập."""
    user1_headers = register("viewer1@example.com")
    user2_headers = register("viewer2@example.com")
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"

    # Viewer 1 xem
    res1 = client.post(url, headers=user1_headers)
    assert res1.json()["counted"] is True
    assert res1.json()["view_count"] == 1

    # Viewer 2 xem -> Được tính view độc lập
    res2 = client.post(url, headers=user2_headers)
    assert res2.json()["counted"] is True
    assert res2.json()["view_count"] == 2

    # Khách vãng lai với IP khác (qua header X-Forwarded-For)
    res3 = client.post(url, headers={"X-Forwarded-For": "203.0.113.195"})
    assert res3.json()["counted"] is True
    assert res3.json()["view_count"] == 3


def test_video_view_cooldown_expiration_resets(client, seed_video, monkeypatch):
    """Sau khi hết thời gian cooldown 5 phút (300 giây), lượt xem tiếp theo được ghi nhận."""
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"

    current_time = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: current_time)

    # Lần 1 tại t=1000s
    res1 = client.post(url)
    assert res1.json()["counted"] is True
    assert res1.json()["view_count"] == 1

    # Lần 2 tại t=1200s (sau 200s < 300s) -> Bị chặn cooldown
    current_time = 1200.0
    res2 = client.post(url)
    assert res2.json()["counted"] is False
    assert res2.json()["view_count"] == 1

    # Lần 3 tại t=1301s (sau 301s > 300s) -> Hết cooldown, được tính view
    current_time = 1301.0
    res3 = client.post(url)
    assert res3.json()["counted"] is True
    assert res3.json()["view_count"] == 2


def test_video_view_not_found_and_deleted(client, login, seed_video):
    """Video không tồn tại hoặc đã bị xóa mềm phải trả về 404."""
    # Video không tồn tại
    res_fake = client.post(f"/api/v1/videos/{uuid4()}/views")
    assert res_fake.status_code == 404

    # Video đã bị soft-deleted bởi chủ sở hữu
    seeded = seed_video(status=VideoStatus.published)
    owner_headers = login(seeded.email)
    del_res = client.delete(f"/api/v1/videos/{seeded.video_id}", headers=owner_headers)
    assert del_res.status_code == 204

    res_deleted = client.post(f"/api/v1/videos/{seeded.video_id}/views")
    assert res_deleted.status_code == 404


def test_video_view_concurrency_race_condition(client, seed_video):
    """
    Giả lập 5 request tính view gửi đồng thời cùng một lúc từ cùng một User/IP.
    Kỳ vọng:
    - Chỉ DUY NHẤT 1 request được ghi nhận (counted = True).
    - 4 request còn lại phải bị chặn bởi cooldown (counted = False).
    - view_count trong DB chỉ tăng đúng 1 đơn vị (tất cả response đều thấy view_count = 1).
    """
    from concurrent.futures import ThreadPoolExecutor

    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"

    def send_view_request():
        return client.post(url)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_view_request) for _ in range(5)]
        responses = [f.result() for f in futures]

    assert len(responses) == 5
    for resp in responses:
        assert resp.status_code == 200

    counted_true_list = [r for r in responses if r.json()["counted"] is True]
    counted_false_list = [r for r in responses if r.json()["counted"] is False]

    # Duy nhất 1 request được tính view
    assert len(counted_true_list) == 1
    assert counted_true_list[0].json()["view_count"] == 1
    # 4 request bị cooldown chặn
    assert len(counted_false_list) == 4

    # Xác minh view_count trong DB tăng đúng 1 đơn vị
    res_final = client.post(url)
    assert res_final.json()["counted"] is False
    assert res_final.json()["view_count"] == 1


def test_cooldown_cache_ttl_cleanup(client, seed_video, monkeypatch):
    """Xác minh cơ chế tự động dọn dẹp các key đã hết hạn khỏi bộ nhớ (chống Memory Leak)."""
    seeded = seed_video(status=VideoStatus.published)
    url = f"/api/v1/videos/{seeded.video_id}/views"

    current_time = 2000.0
    monkeypatch.setattr(time, "monotonic", lambda: current_time)

    # Gửi view tại t=2000s từ 2 IP khác nhau
    client.post(url, headers={"X-Forwarded-For": "10.0.0.1"})
    client.post(url, headers={"X-Forwarded-For": "10.0.0.2"})
    assert len(view_tracking_service._view_cooldown_cache) == 2

    # Đến t=2350s (đã qua 350s > 300s cooldown và > 60s cleanup interval)
    current_time = 2350.0
    # Gửi 1 view mới từ IP thứ 3 để kích hoạt dọn dẹp cache
    client.post(url, headers={"X-Forwarded-For": "10.0.0.3"})

    # 2 key cũ hết hạn đã được tự động dọn sạch, chỉ còn lại 1 key mới
    assert len(view_tracking_service._view_cooldown_cache) == 1

