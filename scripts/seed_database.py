import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.security import hash_password
from app.services.storage_service import get_storage_service
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine

# ======================================================
# CONFIGURATION
# ======================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

VIDEO_FIXTURES = [
    {
        "title_env": "E2E_VIDEO_01_TITLE",
        "filename": "e2e-video-01.mp4",
    },
    {
        "title_env": "E2E_VIDEO_02_TITLE",
        "filename": "e2e-video-02.mp4",
    },
]


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")

    return value


def validate_environment() -> URL:
    if os.getenv("APP_ENV") != "e2e":
        raise RuntimeError("Seeding is only allowed in E2E environment.")

    raw_url = get_required_env("DATABASE_URL")

    url = make_url(raw_url)

    if url.get_backend_name() != "postgresql":
        raise RuntimeError("E2E database must be PostgreSQL.")

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")

    elif url.drivername != "postgresql+asyncpg":
        raise RuntimeError("Expected PostgreSQL asyncpg driver.")

    query = dict(url.query)

    query.pop("channel_binding", None)

    sslmode = query.pop("sslmode", None)

    if sslmode and "ssl" not in query:
        query["ssl"] = sslmode

    return url.set(query=query)


# ======================================================
# VIDEO FIXTURES
# ======================================================
def resolve_project_path(value: str) -> Path:
    path = Path(value).expanduser()

    if not path.is_absolute():
        path = ROOT_DIR / path

    return path.resolve()


def validate_video_fixtures():
    video_dir = resolve_project_path(get_required_env("E2E_VIDEO_DIR"))

    fixtures = []

    for item in VIDEO_FIXTURES:
        source = video_dir / item["filename"]

        if not source.is_file():
            raise FileNotFoundError(f"Missing video fixture: {source}")

        if source.stat().st_size == 0:
            raise ValueError(f"Video fixture is empty: {source}")

        fixtures.append(
            {
                "title": get_required_env(item["title_env"]),
                "filename": item["filename"],
                "content": source.read_bytes(),
            }
        )

    print(f"Validated {len(fixtures)} video fixtures.")

    return fixtures


# ======================================================
# SEED DATABASE
# ======================================================


async def seed_database():
    database_url = validate_environment()

    user_email = get_required_env("E2E_USER_EMAIL")
    user_password = get_required_env("E2E_USER_PASSWORD")

    moderator_email = get_required_env("E2E_MODERATOR_EMAIL")
    moderator_password = get_required_env("E2E_MODERATOR_PASSWORD")

    # 1. Kiểm tra video trước khi ghi dữ liệu.
    videos = validate_video_fixtures()

    # 2. Hash bằng chính implementation của backend.
    user_password_hash = hash_password(user_password)

    moderator_password_hash = hash_password(moderator_password)

    # 3. Tạo UUID cố định trong phạm vi lần chạy hiện tại.
    user_id = uuid.uuid4()
    moderator_id = uuid.uuid4()

    video_ids = [
        uuid.uuid4(),
        uuid.uuid4(),
    ]

    now = datetime.now(timezone.utc)

    # Video 01 đứng trước Video 02 nếu Feed dùng DESC.
    video_created_at = [
        now - timedelta(seconds=60),
        now,
    ]

    # 4. Upload video thông qua StorageService.
    storage = get_storage_service()

    uploaded_paths = []

    try:
        for video in videos:
            storage_path = storage.upload_file(
                file_key=video["filename"],
                content=video["content"],
                content_type="video/mp4",
            )

            video["storage_path"] = storage_path
            video["size_bytes"] = len(video["content"])

            uploaded_paths.append(storage_path)

        # 5. Tạo kết nối database.
        engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
        )

        try:
            async with engine.begin() as connection:
                # ======================================
                # CREATE USER + MODERATOR
                # ======================================

                await connection.execute(
                    text("""
                        INSERT INTO users (
                            id,
                            email,
                            display_name,
                            password_hash,
                            role,
                            is_active,
                            created_at,
                            discriminator,
                            bio,
                            avatar_url
                        )
                        VALUES (
                            :id,
                            :email,
                            :display_name,
                            :password_hash,
                            CAST(:role AS userrole),
                            TRUE,
                            :created_at,
                            :discriminator,
                            NULL,
                            NULL
                        )
                    """),
                    [
                        {
                            "id": user_id,
                            "email": user_email,
                            "display_name": "E2E User",
                            "password_hash": user_password_hash,
                            "role": "user",
                            "created_at": now,
                            "discriminator": "0001",
                        },
                        {
                            "id": moderator_id,
                            "email": moderator_email,
                            "display_name": "E2E Moderator",
                            "password_hash": moderator_password_hash,
                            "role": "moderator",
                            "created_at": now,
                            "discriminator": "0001",
                        },
                    ],
                )

                print("Created E2E users.")

                # ======================================
                # CREATE VIDEOS
                # ======================================

                for index, video in enumerate(videos):
                    await connection.execute(
                        text("""
                            INSERT INTO videos (
                                id,
                                owner_id,
                                original_filename,
                                storage_path,
                                mime_type,
                                size_bytes,
                                caption,
                                status,
                                is_deleted,
                                created_at,
                                visibility,
                                allow_comments,
                                view_count
                            )
                            VALUES (
                                :id,
                                :owner_id,
                                :original_filename,
                                :storage_path,
                                'video/mp4',
                                :size_bytes,
                                :caption,
                                CAST('published' AS videostatus),
                                FALSE,
                                :created_at,
                                'public',
                                TRUE,
                                0
                            )
                        """),
                        {
                            "id": video_ids[index],
                            "owner_id": user_id,
                            "original_filename": video["filename"],
                            "storage_path": video["storage_path"],
                            "size_bytes": video["size_bytes"],
                            "caption": video["title"],
                            "created_at": video_created_at[index],
                        },
                    )

                print("Created E2E videos.")

                # ======================================
                # CREATE MODERATION REVIEWS
                # ======================================

                for video_id in video_ids:
                    await connection.execute(
                        text("""
                            INSERT INTO moderation_reviews (
                                id,
                                video_id,
                                moderator_id,
                                action,
                                reason,
                                created_at
                            )
                            VALUES (
                                :id,
                                :video_id,
                                :moderator_id,
                                CAST('approve' AS moderationaction),
                                :reason,
                                :created_at
                            )
                        """),
                        {
                            "id": uuid.uuid4(),
                            "video_id": video_id,
                            "moderator_id": moderator_id,
                            "reason": "Approved E2E test fixture.",
                            "created_at": now,
                        },
                    )

                print("Created moderation reviews.")

        finally:
            await engine.dispose()

    except Exception:
        # Nếu seed database lỗi, xóa các file đã upload
        # để tránh để lại video fixture mồ côi.
        for file_path in uploaded_paths:
            try:
                storage.delete_file(file_path)
            except Exception as cleanup_error:
                print(f"WARNING: Cannot cleanup {file_path}: {cleanup_error}")

        raise

    print("====================================")
    print("E2E DATABASE SEED COMPLETED")
    print(f"User: {user_email}")
    print(f"Moderator: {moderator_email}")
    print(f"Videos: {len(videos)}")
    print("====================================")


if __name__ == "__main__":
    asyncio.run(seed_database())
