import base64
import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.core.config import get_settings
from app.models import User


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, encoded_salt, encoded_digest = password_hash.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode())
        expected = base64.urlsafe_b64decode(encoded_digest.encode())
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user: User) -> str:
    settings = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "exp": expires,
        "jti": str(uuid4()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """Giải mã access token; ném ``jwt.PyJWTError`` nếu không hợp lệ."""
    return jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])


def new_opaque_token(nbytes: int = 48) -> str:
    """Token ngẫu nhiên khó đoán cho refresh token / đặt lại mật khẩu."""
    return secrets.token_urlsafe(nbytes)


def hash_opaque_token(raw: str) -> str:
    """Chỉ lưu dạng băm SHA-256 của token trong database."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def opaque_tokens_equal(raw: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_opaque_token(raw), stored_hash)


def as_aware(value: datetime) -> datetime:
    """SQLite trả datetime naive; chuẩn hoá về UTC để so sánh an toàn."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

