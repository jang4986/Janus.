from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import (
    Report,
    ReportStatus,
    UserRole,
    VideoComment,
    VideoLike,
    VideoStatus,
)
from app.schemas import CommentCreate, ReportCreate
from app.services import moderation_service, social_service


def make_user(*, role: UserRole = UserRole.user) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=role)


def allow_published_video(monkeypatch, *, allow_comments: bool = True):
    video = SimpleNamespace(allow_comments=allow_comments)
    monkeypatch.setattr(social_service, "_published_video", lambda *_args: video)
    return video


def test_toggle_like_adds_a_like_for_new_user(monkeypatch):
    allow_published_video(monkeypatch)
    db = Mock()
    db.get.return_value = None
    db.scalar.return_value = 1
    user = make_user()
    video_id = uuid4()

    result = social_service.toggle_like(db, video_id, user)

    assert result.is_liked is True
    assert result.like_count == 1
    added = db.add.call_args.args[0]
    assert isinstance(added, VideoLike)
    assert added.video_id == video_id
    assert added.user_id == user.id
    db.commit.assert_called_once_with()


def test_toggle_like_removes_existing_like(monkeypatch):
    allow_published_video(monkeypatch)
    db = Mock()
    existing_like = object()
    db.get.return_value = existing_like
    db.scalar.return_value = 0

    result = social_service.toggle_like(db, uuid4(), make_user())

    assert result.is_liked is False
    assert result.like_count == 0
    db.delete.assert_called_once_with(existing_like)
    db.commit.assert_called_once_with()


def test_toggle_like_rejects_non_public_video(monkeypatch):
    db = Mock()
    monkeypatch.setattr(
        social_service,
        "_published_video",
        Mock(side_effect=NotFoundError("video not found")),
    )

    with pytest.raises(NotFoundError):
        social_service.toggle_like(db, uuid4(), make_user())

    db.get.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_comment_trims_content_and_sets_author(monkeypatch):
    allow_published_video(monkeypatch)
    db = Mock()
    user = make_user()
    video_id = uuid4()

    result = social_service.create_comment(
        db, video_id, user, CommentCreate(content="  Hello  ")
    )

    assert isinstance(result, VideoComment)
    assert result.content == "Hello"
    assert result.video_id == video_id
    assert result.author_id == user.id
    assert result.author is user
    db.add.assert_called_once_with(result)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(result)


def test_create_comment_rejects_disabled_comments(monkeypatch):
    allow_published_video(monkeypatch, allow_comments=False)
    db = Mock()

    with pytest.raises(ForbiddenError):
        social_service.create_comment(
            db, uuid4(), make_user(), CommentCreate(content="Hello")
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("content", ["", "   "])
def test_comment_schema_rejects_empty_or_whitespace_content(content):
    with pytest.raises(ValidationError):
        CommentCreate(content=content)


@pytest.mark.parametrize("delete_as_video_owner", [False, True])
def test_delete_comment_allows_author_or_video_owner(delete_as_video_owner):
    author_id = uuid4()
    caller = make_user()
    comment = SimpleNamespace(
        id=uuid4(),
        video_id=uuid4(),
        author_id=author_id,
        content="comment",
        is_deleted=False,
    )
    video = SimpleNamespace(owner_id=caller.id if delete_as_video_owner else uuid4())
    if not delete_as_video_owner:
        caller.id = author_id
    db = Mock()
    db.scalar.return_value = comment
    db.get.return_value = video

    result = social_service.delete_comment(db, comment.id, caller)

    assert result is None
    assert comment.is_deleted is True
    assert comment.content is None
    db.commit.assert_called_once_with()


def test_delete_comment_rejects_user_without_permission():
    comment = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), author_id=uuid4(), content="comment", is_deleted=False
    )
    video = SimpleNamespace(owner_id=uuid4())
    db = Mock()
    db.scalar.return_value = comment
    db.get.return_value = video

    with pytest.raises(ForbiddenError):
        social_service.delete_comment(db, comment.id, make_user())

    assert comment.is_deleted is False
    assert comment.content == "comment"
    db.commit.assert_not_called()


def report_test_context(*, video_status=VideoStatus.published, is_deleted=False):
    video = SimpleNamespace(status=video_status, is_deleted=is_deleted)
    db = Mock()
    db.get.return_value = video
    db.scalar.return_value = None
    return db, video


def test_create_report_adds_report_and_moves_published_video_to_review():
    db, video = report_test_context()
    video_id = uuid4()
    reporter = make_user()

    result = moderation_service.create_report(db, video_id, reporter, "Inappropriate content")

    assert isinstance(result, Report)
    assert result.video_id == video_id
    assert result.reporter_id == reporter.id
    assert result.reason == "Inappropriate content"
    assert video.status == VideoStatus.pending_review
    assert Report.__table__.c.status.default.arg == ReportStatus.open
    db.add.assert_called_once_with(result)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(result)


def test_create_report_rejects_duplicate_open_report():
    db, _video = report_test_context()
    db.scalar.return_value = object()

    with pytest.raises(ConflictError):
        moderation_service.create_report(db, uuid4(), make_user(), "Duplicate report")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_report_rejects_missing_video():
    db = Mock()
    db.get.return_value = None

    with pytest.raises(NotFoundError):
        moderation_service.create_report(db, uuid4(), make_user(), "Valid report")

    db.scalar.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_report_rejects_soft_deleted_video():
    db, _video = report_test_context(is_deleted=True)

    with pytest.raises(NotFoundError):
        moderation_service.create_report(db, uuid4(), make_user(), "Valid report")

    db.scalar.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    ("initial_status", "expected_status"),
    [
        (VideoStatus.published, VideoStatus.pending_review),
        (VideoStatus.processing, VideoStatus.processing),
    ],
)
def test_create_report_updates_only_published_video(initial_status, expected_status):
    db, video = report_test_context(video_status=initial_status)

    moderation_service.create_report(db, uuid4(), make_user(), "Valid report")

    assert video.status == expected_status
    db.commit.assert_called_once_with()


@pytest.mark.parametrize("reason", ["ab", "x" * 1001])
def test_report_schema_rejects_reason_outside_length_limits(reason):
    with pytest.raises(ValidationError):
        ReportCreate(reason=reason)
