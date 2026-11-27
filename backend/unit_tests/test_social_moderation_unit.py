from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.exceptions import ConflictError, ForbiddenError, InvalidInputError, NotFoundError
from app.models import (
    Appeal,
    AppealStatus,
    ModerationAction,
    ModerationReview,
    Report,
    ReportStatus,
    UserRole,
    VideoComment,
    VideoLike,
    VideoStatus,
)
from app.schemas import AppealCreate, CommentCreate, ReportCreate
from app.services import moderation_service, social_service


def make_user(*, role: UserRole = UserRole.user) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=role)


def make_video(
    *,
    status: VideoStatus = VideoStatus.published,
    is_deleted: bool = False,
    allow_comments: bool = True,
    owner_id=None,
) -> SimpleNamespace:
    v = SimpleNamespace(
        id=uuid4(),
        status=status,
        is_deleted=is_deleted,
        allow_comments=allow_comments,
        owner_id=owner_id or uuid4(),
    )
    return v


def allow_published_video(monkeypatch, *, allow_comments: bool = True):
    video = SimpleNamespace(allow_comments=allow_comments)
    monkeypatch.setattr(social_service, "_published_video", lambda *_args: video)
    return video


# =============================================================================
# TOGGLE LIKE TESTS (Equivalence Partitioning + Boundary Value Analysis)
# =============================================================================

# Partition: User Role
# - Valid: UserRole.user -> should succeed
# - Invalid: UserRole.moderator, UserRole.admin -> ForbiddenError (chỉ user thường được like)

# Partition: Video State
# - Valid: published, not deleted -> should succeed
# - Invalid: not published, deleted, not found -> NotFoundError

# Partition: Like State
# - No existing like -> add like
# - Existing like -> remove like


def test_toggle_like_adds_a_like_for_new_user(monkeypatch):
    allow_published_video(monkeypatch)
    db = Mock()
    db.get.return_value = None
    db.scalar.return_value = 1

    user_id = UUID("11111111-1111-1111-1111-111111111111")
    video_id = UUID("22222222-2222-2222-2222-222222222222")
    user = SimpleNamespace(id=user_id, role=UserRole.user)

    print("\n" + "=" * 60)
    print("[INPUT DATA - DỮ LIỆU ĐẦU VÀO]")
    print(f"  * User ID          : {user.id}")
    print(f"  * User Role        : {user.role.value}")
    print(f"  * Video ID         : {video_id}")
    print(f"  * Like hiện tại    : None (User chưa từng like video này)")
    print(f"  * Giả lập đếm DB   : 1 like (khi query count)")

    result = social_service.toggle_like(db, video_id, user)

    added = db.add.call_args.args[0]
    print("\n[OUTPUT DATA - KẾT QUẢ ĐẠT ĐƯỢC]")
    print(f"  * result.is_liked  : {result.is_liked} (Đã thích)")
    print(f"  * result.like_count: {result.like_count}")
    print(f"  * Bản ghi DB thêm  : {type(added).__name__}")
    print(f"    - video_id       : {added.video_id}")
    print(f"    - user_id        : {added.user_id}")
    print(f"  * db.commit()      : Đã được gọi (Lưu DB thành công)")
    print("=" * 60)

    assert result.is_liked is True
    assert result.like_count == 1
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


# Boundary: like count values
@pytest.mark.parametrize("like_count", [0, 1, 99, 100, 1000])
def test_toggle_like_like_count_boundaries(monkeypatch, like_count):
    allow_published_video(monkeypatch)
    db = Mock()
    db.get.return_value = None
    db.scalar.return_value = like_count
    user = make_user()
    video_id = uuid4()

    result = social_service.toggle_like(db, video_id, user)

    assert result.is_liked is True
    assert result.like_count == like_count


# Equivalence partition: video status (published vs other statuses)
@pytest.mark.parametrize(
    "video_status",
    [
        VideoStatus.published,
        VideoStatus.processing,
        VideoStatus.pending_review,
        VideoStatus.rejected,
        VideoStatus.failed,
    ],
)
def test_toggle_like_only_allows_published_video(monkeypatch, video_status):
    db = Mock()
    video = make_video(status=video_status)

    def mock_published_video(*args):
        if video_status != VideoStatus.published:
            raise NotFoundError("video not found")
        return SimpleNamespace(allow_comments=True)

    monkeypatch.setattr(social_service, "_published_video", mock_published_video)

    if video_status == VideoStatus.published:
        db.get.return_value = None
        db.scalar.return_value = 1
        result = social_service.toggle_like(db, uuid4(), make_user())
        assert result.is_liked is True
    else:
        with pytest.raises(NotFoundError):
            social_service.toggle_like(db, uuid4(), make_user())


# =============================================================================
# ROLE-BASED ACCESS CONTROL (IMPLEMENTED)
# =============================================================================
# Moderator/Admin không được like, bookmark, comment - chỉ user thường mới được.

@pytest.mark.parametrize("role", [UserRole.moderator, UserRole.admin])
def test_toggle_like_rejects_moderator_and_admin(monkeypatch, role):
    """moderator/admin không được like"""
    allow_published_video(monkeypatch)
    db = Mock()

    with pytest.raises(ForbiddenError):
        social_service.toggle_like(db, uuid4(), make_user(role=role))

    db.get.assert_not_called()
    db.add.assert_not_called()
    db.delete.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("role", [UserRole.moderator, UserRole.admin])
def test_toggle_bookmark_rejects_moderator_and_admin(monkeypatch, role):
    """moderator/admin không được bookmark"""
    allow_published_video(monkeypatch)
    db = Mock()

    with pytest.raises(ForbiddenError):
        social_service.toggle_bookmark(db, uuid4(), make_user(role=role))

    db.get.assert_not_called()
    db.add.assert_not_called()
    db.delete.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("role", [UserRole.moderator, UserRole.admin])
def test_create_comment_rejects_moderator_and_admin(monkeypatch, role):
    """moderator/admin không được comment"""
    allow_published_video(monkeypatch)
    db = Mock()

    with pytest.raises(ForbiddenError):
        social_service.create_comment(
            db,
            uuid4(),
            make_user(role=role),
            CommentCreate(content="Không được bình luận"),
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


# =============================================================================
# CREATE COMMENT TESTS (Equivalence Partitioning + Boundary Value Analysis)
# =============================================================================

# Partition: User Role
# - Valid: UserRole.user -> should succeed
# - Invalid: UserRole.moderator, UserRole.admin -> ForbiddenError

# Partition: Video State
# - Valid: published, not deleted, allow_comments=True -> should succeed
# - Invalid: not published, deleted, allow_comments=False -> should raise error

# Partition: Comment Content (boundary)
# - Empty string -> ValidationError (schema)
# - Whitespace only -> ValidationError (schema)
# - 1 char -> Valid
# - 500 chars -> Valid (max)
# - 501 chars -> ValidationError (schema)
# - Content with leading/trailing whitespace -> should be trimmed


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


# Schema boundary tests
@pytest.mark.parametrize("content", ["", "   ", "x" * 501])
def test_comment_schema_rejects_empty_or_whitespace_or_over_limit_content(content):
    with pytest.raises(ValidationError):
        CommentCreate(content=content)


@pytest.mark.parametrize("content", ["x", "x" * 500])
def test_comment_schema_accepts_length_boundaries(content):
    result = CommentCreate(content=content)
    assert result.content == content


# Equivalence partition: video status
@pytest.mark.parametrize(
    "video_status,expect_success",
    [
        (VideoStatus.published, True),
        (VideoStatus.processing, False),
        (VideoStatus.pending_review, False),
        (VideoStatus.rejected, False),
        (VideoStatus.failed, False),
    ],
)
def test_create_comment_only_allows_published_video(monkeypatch, video_status, expect_success):
    db = Mock()
    video = make_video(status=video_status)

    def mock_published_video(*args):
        if video_status != VideoStatus.published:
            raise NotFoundError("video not found")
        return SimpleNamespace(allow_comments=True)

    monkeypatch.setattr(social_service, "_published_video", mock_published_video)

    if expect_success:
        result = social_service.create_comment(
            db, uuid4(), make_user(), CommentCreate(content="Valid comment")
        )
        assert isinstance(result, VideoComment)
        assert result.content == "Valid comment"
    else:
        with pytest.raises(NotFoundError):
            social_service.create_comment(
                db, uuid4(), make_user(), CommentCreate(content="Valid comment")
            )


# Equivalence partition: allow_comments flag
@pytest.mark.parametrize("allow_comments,expect_success", [(True, True), (False, False)])
def test_create_comment_respects_allow_comments_flag(monkeypatch, allow_comments, expect_success):
    allow_published_video(monkeypatch, allow_comments=allow_comments)
    db = Mock()

    if expect_success:
        result = social_service.create_comment(
            db, uuid4(), make_user(), CommentCreate(content="Valid comment")
        )
        assert isinstance(result, VideoComment)
    else:
        with pytest.raises(ForbiddenError):
            social_service.create_comment(
                db, uuid4(), make_user(), CommentCreate(content="Valid comment")
            )


# =============================================================================
# DELETE COMMENT TESTS (Equivalence Partitioning + Boundary Value Analysis)
# =============================================================================

# Partition: Delete Permission
# - Author of comment -> can delete
# - Video owner -> can delete
# - Moderator -> can delete
# - Admin -> can delete
# - Other user -> ForbiddenError

# Partition: Comment State
# - Not deleted -> can delete
# - Already deleted -> NotFoundError (not found by query)


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


@pytest.mark.parametrize("role", [UserRole.moderator, UserRole.admin])
def test_delete_comment_allows_moderator_and_admin(role):
    comment = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), author_id=uuid4(), content="comment", is_deleted=False
    )
    video = SimpleNamespace(owner_id=uuid4())
    db = Mock()
    db.scalar.return_value = comment
    db.get.return_value = video

    result = social_service.delete_comment(db, comment.id, make_user(role=role))

    assert result is None
    assert comment.is_deleted is True
    assert comment.content is None
    db.commit.assert_called_once_with()


def test_delete_comment_rejects_already_deleted_comment():
    comment = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), author_id=uuid4(), content="comment", is_deleted=True
    )
    db = Mock()
    # scalar returns None because query filters is_deleted=False
    db.scalar.return_value = None

    with pytest.raises(NotFoundError):
        social_service.delete_comment(db, comment.id, make_user())

    db.commit.assert_not_called()


def test_delete_comment_rejects_missing_comment():
    db = Mock()
    db.scalar.return_value = None

    with pytest.raises(NotFoundError):
        social_service.delete_comment(db, uuid4(), make_user())

    db.commit.assert_not_called()


# =============================================================================
# CREATE REPORT TESTS (Equivalence Partitioning + Boundary Value Analysis)
# =============================================================================

# Partition: Video State
# - Published, not deleted -> should succeed, change status to pending_review
# - Processing, pending_review, rejected, failed -> should succeed, no status change
# - Deleted -> NotFoundError
# - Not found -> NotFoundError

# Partition: Report State
# - No existing report -> should succeed
# - Existing open report -> ConflictError

# Partition: Reason Length (boundary)
# - Empty -> ValidationError
# - 1-2 chars -> ValidationError (min 3)
# - 3 chars -> Valid
# - 1000 chars -> Valid (max)
# - 1001 chars -> ValidationError
# - Whitespace only -> ValidationError


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
        (VideoStatus.pending_review, VideoStatus.pending_review),
        (VideoStatus.rejected, VideoStatus.rejected),
        (VideoStatus.failed, VideoStatus.failed),
    ],
)
def test_create_report_updates_only_published_video(initial_status, expected_status):
    db, video = report_test_context(video_status=initial_status)

    moderation_service.create_report(db, uuid4(), make_user(), "Valid report")

    assert video.status == expected_status
    db.commit.assert_called_once_with()


# Schema boundary tests
@pytest.mark.parametrize("reason", ["", "ab", "x" * 1001])
def test_report_schema_rejects_reason_outside_length_limits(reason):
    with pytest.raises(ValidationError):
        ReportCreate(reason=reason)


@pytest.mark.parametrize("reason", ["abc", "x" * 1000])
def test_report_schema_accepts_length_boundaries(reason):
    result = ReportCreate(reason=reason)
    assert result.reason == reason


# Equivalence partition: reporter role (should be allowed for all roles)
@pytest.mark.parametrize("role", [UserRole.user, UserRole.moderator, UserRole.admin])
def test_create_report_allows_all_roles(role):
    db, video = report_test_context()

    result = moderation_service.create_report(db, uuid4(), make_user(role=role), "Valid report")

    assert isinstance(result, Report)
    assert result.reporter_id is not None


# =============================================================================
# ADDITIONAL SERVICE TESTS: TOGGLE BOOKMARK, TOGGLE FOLLOW
# =============================================================================

# Partition: User Role
# - Valid: UserRole.user, UserRole.moderator, UserRole.admin -> all can bookmark (service has no role check)

def test_toggle_bookmark_adds_for_new_user(monkeypatch):
    allow_published_video(monkeypatch)
    db = Mock()
    db.get.return_value = None
    user = make_user()
    video_id = uuid4()

    result = social_service.toggle_bookmark(db, video_id, user)

    assert result.is_bookmarked is True
    added = db.add.call_args.args[0]
    assert isinstance(added, object)  # VideoBookmark
    db.commit.assert_called_once_with()


def test_toggle_bookmark_removes_existing(monkeypatch):
    allow_published_video(monkeypatch)
    db = Mock()
    existing_bookmark = object()
    db.get.return_value = existing_bookmark

    result = social_service.toggle_bookmark(db, uuid4(), make_user())

    assert result.is_bookmarked is False
    db.delete.assert_called_once_with(existing_bookmark)
    db.commit.assert_called_once_with()


def test_toggle_follow_adds_for_new_user():
    db = Mock()
    target = SimpleNamespace(id=uuid4(), is_active=True)
    db.get.side_effect = [target, None]  # target user, then follow check

    result = social_service.toggle_follow(db, target.id, make_user())

    assert result.is_following is True
    added = db.add.call_args.args[0]
    assert isinstance(added, object)  # UserFollow
    db.commit.assert_called_once_with()


def test_toggle_follow_removes_existing():
    db = Mock()
    target = SimpleNamespace(id=uuid4(), is_active=True)
    existing_follow = object()
    db.get.side_effect = [target, existing_follow]

    result = social_service.toggle_follow(db, target.id, make_user())

    assert result.is_following is False
    db.delete.assert_called_once_with(existing_follow)
    db.commit.assert_called_once_with()


def test_toggle_follow_rejects_self_follow():
    db = Mock()
    user = make_user()

    with pytest.raises(InvalidInputError):
        social_service.toggle_follow(db, user.id, user)

    db.get.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_toggle_follow_rejects_missing_target():
    db = Mock()
    db.get.return_value = None

    with pytest.raises(NotFoundError):
        social_service.toggle_follow(db, uuid4(), make_user())

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_toggle_follow_rejects_inactive_target():
    db = Mock()
    db.get.return_value = SimpleNamespace(id=uuid4(), is_active=False)

    with pytest.raises(NotFoundError):
        social_service.toggle_follow(db, uuid4(), make_user())

    db.add.assert_not_called()
    db.commit.assert_not_called()


# =============================================================================
# MODERATION SERVICE ADDITIONAL TESTS
# =============================================================================

def test_decide_video_approves_and_publishes():
    video = SimpleNamespace(id=uuid4(), status=VideoStatus.pending_review, is_deleted=False)
    db = Mock()
    db.get.return_value = video
    moderator = make_user(role=UserRole.moderator)

    moderation_service.decide_video(db, video.id, moderator, ModerationAction.approve, "OK")

    assert video.status == VideoStatus.published
    db.add.assert_called_once()
    review = db.add.call_args.args[0]
    assert isinstance(review, ModerationReview)
    assert review.action == ModerationAction.approve
    assert review.moderator_id == moderator.id
    db.commit.assert_called_once_with()


def test_decide_video_rejects_and_requires_reason():
    video = SimpleNamespace(id=uuid4(), status=VideoStatus.pending_review, is_deleted=False)
    db = Mock()
    db.get.return_value = video
    moderator = make_user(role=UserRole.moderator)

    with pytest.raises(InvalidInputError):
        moderation_service.decide_video(db, video.id, moderator, ModerationAction.reject, "")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_decide_video_rejects_with_valid_reason():
    video = SimpleNamespace(id=uuid4(), status=VideoStatus.pending_review, is_deleted=False)
    db = Mock()
    db.get.return_value = video
    moderator = make_user(role=UserRole.moderator)

    moderation_service.decide_video(db, video.id, moderator, ModerationAction.reject, "Violation")

    assert video.status == VideoStatus.rejected
    db.add.assert_called_once()
    review = db.add.call_args.args[0]
    assert review.action == ModerationAction.reject
    assert review.reason == "Violation"
    db.commit.assert_called_once_with()


def test_decide_video_rejects_missing_video():
    db = Mock()
    db.get.return_value = None

    with pytest.raises(NotFoundError):
        moderation_service.decide_video(db, uuid4(), make_user(role=UserRole.moderator), ModerationAction.approve, "OK")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_decide_video_rejects_soft_deleted_video():
    video = SimpleNamespace(id=uuid4(), status=VideoStatus.pending_review, is_deleted=True)
    db = Mock()
    db.get.return_value = video

    with pytest.raises(NotFoundError):
        moderation_service.decide_video(db, video.id, make_user(role=UserRole.moderator), ModerationAction.approve, "OK")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_decide_report_resolves_and_publishes_video():
    """reject action = report rejected, video published (video is OK)"""
    report = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), status=ReportStatus.open
    )
    video = SimpleNamespace(id=report.video_id, status=VideoStatus.pending_review)
    db = Mock()
    db.get.side_effect = [report, video]
    moderator = make_user(role=UserRole.moderator)

    moderation_service.decide_report(db, report.id, moderator, ModerationAction.reject, "Not a violation")

    assert report.status == ReportStatus.resolved
    assert video.status == VideoStatus.published
    db.commit.assert_called_once_with()


def test_decide_report_approves_and_rejects_video():
    """approve action = report approved, video rejected (video is violating)"""
    report = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), status=ReportStatus.open
    )
    video = SimpleNamespace(id=report.video_id, status=VideoStatus.published)
    db = Mock()
    db.get.side_effect = [report, video]
    moderator = make_user(role=UserRole.moderator)

    moderation_service.decide_report(db, report.id, moderator, ModerationAction.approve, "Confirmed violation")

    assert report.status == ReportStatus.rejected
    assert video.status == VideoStatus.rejected
    db.commit.assert_called_once_with()


def test_decide_report_rejects_closed_report():
    report = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), status=ReportStatus.resolved
    )
    db = Mock()
    db.get.return_value = report

    with pytest.raises(NotFoundError):
        moderation_service.decide_report(db, report.id, make_user(role=UserRole.moderator), ModerationAction.approve, "OK")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_decide_report_rejects_missing_video():
    report = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), status=ReportStatus.open
    )
    db = Mock()
    db.get.side_effect = [report, None]

    with pytest.raises(NotFoundError):
        moderation_service.decide_report(db, report.id, make_user(role=UserRole.moderator), ModerationAction.approve, "OK")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_appeal_by_video_owner():
    video = SimpleNamespace(
        id=uuid4(),
        owner_id=uuid4(),
        status=VideoStatus.rejected,
        is_deleted=False,
    )
    owner_id = video.owner_id
    db = Mock()
    db.get.return_value = video
    db.scalar.return_value = None
    user = make_user()
    user.id = owner_id

    result = moderation_service.create_appeal(db, video.id, user, "Unfair rejection")

    assert isinstance(result, Appeal)
    assert result.video_id == video.id
    assert result.user_id == owner_id
    assert result.reason == "Unfair rejection"
    assert result.status == AppealStatus.open
    db.add.assert_called_once_with(result)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(result)


def test_create_appeal_rejects_non_owner():
    video = SimpleNamespace(
        id=uuid4(),
        owner_id=uuid4(),
        status=VideoStatus.rejected,
        is_deleted=False,
    )
    db = Mock()
    db.get.return_value = video

    with pytest.raises(NotFoundError):
        moderation_service.create_appeal(db, video.id, make_user(), "Unfair rejection")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_appeal_rejects_non_rejected_video():
    video = SimpleNamespace(
        id=uuid4(),
        owner_id=uuid4(),
        status=VideoStatus.published,
        is_deleted=False,
    )
    owner_id = video.owner_id
    db = Mock()
    db.get.return_value = video
    user = make_user()
    user.id = owner_id

    with pytest.raises(InvalidInputError):
        moderation_service.create_appeal(db, video.id, user, "Unfair rejection")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_appeal_rejects_duplicate_open_appeal():
    video = SimpleNamespace(
        id=uuid4(),
        owner_id=uuid4(),
        status=VideoStatus.rejected,
        is_deleted=False,
    )
    owner_id = video.owner_id
    db = Mock()
    db.get.return_value = video
    db.scalar.return_value = object()  # existing appeal
    user = make_user()
    user.id = owner_id

    with pytest.raises(ConflictError):
        moderation_service.create_appeal(db, video.id, user, "Unfair rejection")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_decide_appeal_approves_and_publishes():
    appeal = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), status=AppealStatus.open, user_id=uuid4()
    )
    video = SimpleNamespace(id=appeal.video_id, status=VideoStatus.rejected, is_deleted=False)
    db = Mock()
    db.get.side_effect = [appeal, video]
    moderator = make_user(role=UserRole.moderator)

    moderation_service.decide_appeal(db, appeal.id, moderator, ModerationAction.approve, "Appeal accepted")

    assert appeal.status == AppealStatus.approved
    assert appeal.moderator_id == moderator.id
    assert appeal.decision_reason == "Appeal accepted"
    assert video.status == VideoStatus.published
    db.commit.assert_called_once_with()


def test_decide_appeal_rejects():
    appeal = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), status=AppealStatus.open, user_id=uuid4()
    )
    video = SimpleNamespace(id=appeal.video_id, status=VideoStatus.rejected, is_deleted=False)
    db = Mock()
    db.get.side_effect = [appeal, video]
    moderator = make_user(role=UserRole.moderator)

    moderation_service.decide_appeal(db, appeal.id, moderator, ModerationAction.reject, "Appeal denied")

    assert appeal.status == AppealStatus.rejected
    assert appeal.moderator_id == moderator.id
    assert video.status == VideoStatus.rejected
    db.commit.assert_called_once_with()


def test_decide_appeal_rejects_already_decided():
    appeal = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), status=AppealStatus.approved, user_id=uuid4()
    )
    db = Mock()
    db.get.return_value = appeal

    with pytest.raises(ConflictError):
        moderation_service.decide_appeal(db, appeal.id, make_user(role=UserRole.moderator), ModerationAction.approve, "OK")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_decide_appeal_rejects_missing_appeal():
    db = Mock()
    db.get.return_value = None

    with pytest.raises(NotFoundError):
        moderation_service.decide_appeal(db, uuid4(), make_user(role=UserRole.moderator), ModerationAction.approve, "OK")

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_decide_appeal_rejects_missing_video():
    appeal = SimpleNamespace(
        id=uuid4(), video_id=uuid4(), status=AppealStatus.open, user_id=uuid4()
    )
    db = Mock()
    db.get.side_effect = [appeal, None]

    with pytest.raises(NotFoundError):
        moderation_service.decide_appeal(db, appeal.id, make_user(role=UserRole.moderator), ModerationAction.approve, "OK")

    db.add.assert_not_called()
    db.commit.assert_not_called()


# =============================================================================
# PAGINATION TESTS (Equivalence Partitioning + Boundary Value Analysis)
# =============================================================================

@pytest.mark.parametrize(
    ("input_page", "input_page_size", "expected_page", "expected_page_size", "expected_offset"),
    [
        # Biên dưới của page (page <= 0 được chuẩn hóa về 1)
        (-10, 20, 1, 20, 0),
        (0, 20, 1, 20, 0),
        (1, 20, 1, 20, 0),
        (2, 20, 2, 20, 20),
        # Biên dưới của page_size (page_size <= 0 được chuẩn hóa về 1)
        (1, -5, 1, 1, 0),
        (1, 0, 1, 1, 0),
        (1, 1, 1, 1, 0),
        (1, 2, 1, 2, 0),
        # Biên trên của page_size (MAX_PAGE_SIZE = 100)
        (1, 99, 1, 99, 0),
        (1, 100, 1, 100, 0),
        (1, 101, 1, 100, 0),
        (1, 1000, 1, 100, 0),
        # Kết hợp phân trang thông thường và lớn
        (5, 50, 5, 50, 200),
        (10, 100, 10, 100, 900),
    ],
)
def test_social_pagination_boundaries_and_partitions(
    input_page, input_page_size, expected_page, expected_page_size, expected_offset
):
    """Kiểm tra phân trang: phân vùng tương đương và phân tích giá trị biên cho page và page_size."""
    page, page_size, offset = social_service._page(input_page, input_page_size)
    assert page == expected_page
    assert page_size == expected_page_size
    assert offset == expected_offset


# =============================================================================
# APPEAL SCHEMA BOUNDARY TESTS (Equivalence Partitioning + Boundary Value Analysis)
# =============================================================================

@pytest.mark.parametrize(
    ("reason", "is_valid"),
    [
        # Phân vùng không hợp lệ & giá trị biên dưới (độ dài 0 < min_length 1)
        ("", False),
        # Giá trị biên dưới hợp lệ (min_length = 1)
        ("x", True),
        ("xy", True),
        # Phân vùng hợp lệ thông thường
        ("Lý do khiếu nại hợp lệ", True),
        ("a" * 500, True),
        # Giá trị biên trên hợp lệ (max_length = 1000)
        ("a" * 999, True),
        ("a" * 1000, True),
        # Phân vùng không hợp lệ & giá trị vượt biên trên (1001 > 1000)
        ("a" * 1001, False),
    ],
)
def test_appeal_schema_boundaries_and_partitions(reason, is_valid):
    """Kiểm tra schema AppealCreate: phân vùng tương đương và giá trị biên độ dài reason (1 - 1000)."""
    if is_valid:
        appeal_data = AppealCreate(reason=reason)
        assert appeal_data.reason == reason
    else:
        with pytest.raises(ValidationError):
            AppealCreate(reason=reason)
