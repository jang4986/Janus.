from uuid import UUID

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import (
    Report,
    ReportStatus,
    UserRole,
    Video,
    VideoComment,
    VideoLike,
    VideoStatus,
)


def test_like_and_comment_survive_report_and_rejection(client, seed_video, register):
    video = seed_video(status=VideoStatus.published)
    actor = register("actor@example.com")
    reporter = register("reporter@example.com")
    moderator = register("moderator@example.com", role=UserRole.moderator)

    video_id = str(video.video_id)

    liked = client.post(
        f"/api/v1/videos/{video_id}/like",
        headers=actor,
    )
    assert liked.status_code == 200
    assert liked.json() == {"is_liked": True, "like_count": 1}

    created_comment = client.post(
        f"/api/v1/videos/{video_id}/comments",
        headers=actor,
        json={"content": "Like trước, bình luận trước khi bị báo cáo"},
    )
    assert created_comment.status_code == 201
    comment_id = created_comment.json()["id"]

    report = client.post(
        f"/api/v1/videos/{video_id}/reports",
        headers=reporter,
        json={"reason": "Báo cáo để kiểm tra vòng đời tương tác"},
    )
    assert report.status_code == 201

    # Video đang chờ kiểm duyệt nên comment API không cho xem.
    assert client.get(f"/api/v1/videos/{video_id}/comments").status_code == 404

    # Báo cáo không được xóa like/comment đã lưu.
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoLike)
                .where(VideoLike.video_id == video.video_id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoComment)
                .where(
                    VideoComment.video_id == video.video_id,
                    VideoComment.is_deleted.is_(False),
                )
            )
            == 1
        )

    decision = client.post(
        f"/api/v1/moderation/reports/{report.json()['id']}/decision",
        headers=moderator,
        json={"action": "reject", "reason": "Báo cáo không có căn cứ"},
    )
    assert decision.status_code == 204

    # Khi video được công khai lại, comment cũ vẫn tải được.
    comments = client.get(f"/api/v1/videos/{video_id}/comments")
    assert comments.status_code == 200
    assert any(
        item["id"] == comment_id
        and item["content"] == "Like trước, bình luận trước khi bị báo cáo"
        for item in comments.json()["items"]
    )

    with SessionLocal() as db:
        assert db.get(Video, video.video_id).status is VideoStatus.published
        assert db.get(Report, UUID(report.json()["id"])).status is ReportStatus.resolved
        assert (
            db.scalar(
                select(func.count())
                .select_from(VideoLike)
                .where(VideoLike.video_id == video.video_id)
            )
            == 1
        )
