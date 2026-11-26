import os
from pathlib import Path
from tempfile import gettempdir
from types import SimpleNamespace
from uuid import uuid4

TEST_RUNTIME_PATH = Path(gettempdir()) / f"pbl6-pytest-{os.getpid()}"
TEST_RUNTIME_PATH.mkdir(parents=True, exist_ok=True)
TEST_DB_PATH = TEST_RUNTIME_PATH / "test.db"
TEST_STORAGE_PATH = TEST_RUNTIME_PATH / "storage"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["UPLOAD_DIR"] = str(TEST_STORAGE_PATH)
os.environ["STORAGE_DRIVER"] = "local"
os.environ["AI_ANALYSIS_MODE"] = "auto"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models import AIJob, User, UserRole, Video, VideoStatus

engine = create_engine(
    f"sqlite:///{TEST_DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
TEST_DATASET = Path(__file__).resolve().parents[2] / "local" / "TestDataset-v2"


@pytest.fixture
def real_video_path() -> Path:
    videos = sorted(TEST_DATASET.rglob("*.mp4"))
    if not videos:
        pytest.skip(f"Cần bộ dữ liệu video cục bộ tại {TEST_DATASET}")
    return videos[0]


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def login(client):
    """Đăng nhập và trả về header Authorization."""

    def _login(email: str, password: str = "password123") -> dict[str, str]:
        token = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        ).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login


@pytest.fixture
def register(client, login):
    """Tạo tài khoản (nâng vai trò nếu cần) và trả về header JWT."""

    def _register(
        email: str,
        role: UserRole = UserRole.user,
        password: str = "password123",
    ) -> dict[str, str]:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "display_name": email.split("@")[0],
                "password": password,
            },
        )
        if role is not UserRole.user:
            with TestingSessionLocal() as db:
                user = db.query(User).filter(User.email == email).one()
                user.role = role
                db.commit()
        return login(email, password)

    return _register


@pytest.fixture
def seed_video(tmp_path):
    """Tạo trực tiếp user + video (+AIJob) trong DB test, trả về info cần thiết."""

    def _seed(
        status: VideoStatus = VideoStatus.published,
        caption: str = "video test",
        write_file: bool = True,
        suffix: str = ".mp4",
    ) -> SimpleNamespace:
        email = f"owner-{uuid4().hex[:8]}@example.com"
        path = tmp_path / f"{uuid4().hex}{suffix}"
        if write_file:
            path.write_bytes(b"\x00" * 32)
        with TestingSessionLocal() as db:
            user = User(
                email=email,
                display_name="Owner",
                password_hash=hash_password("password123"),
            )
            db.add(user)
            db.flush()
            video = Video(
                owner_id=user.id,
                original_filename=path.name,
                storage_path=str(path),
                mime_type="video/mp4",
                size_bytes=path.stat().st_size if write_file else 32,
                caption=caption,
                status=status,
            )
            db.add(video)
            db.flush()
            db.add(AIJob(video_id=video.id))
            db.commit()
            return SimpleNamespace(
                user_id=user.id,
                email=email,
                video_id=video.id,
                path=path,
                status=status,
            )

    return _seed
