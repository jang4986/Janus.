"""Unified local and S3-compatible object storage access."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.validate_storage_config()
        self.driver = self.settings.storage_driver.strip().lower()
        self._client = None
        if self.driver == "s3":
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.s3_endpoint_url,
                aws_access_key_id=self.settings.s3_access_key_id,
                aws_secret_access_key=self.settings.s3_secret_access_key,
                region_name=self.settings.s3_region,
                config=Config(signature_version="s3v4"),
            )

    @property
    def is_s3(self) -> bool:
        return self.driver == "s3"

    def upload_file(self, file_key: str, content: bytes, content_type: str) -> str:
        if self.is_s3:
            self._client.put_object(
                Bucket=self.settings.s3_bucket_name,
                Key=file_key,
                Body=content,
                ContentType=content_type,
            )
            return file_key
        path = Path(self.settings.upload_dir) / file_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def upload_thumbnail(
        self, file_key: str, content: bytes, content_type: str = "image/jpeg"
    ) -> str:
        return self.upload_file(file_key, content, content_type)

    def delete_file(self, file_key: str) -> None:
        if self.is_s3 and not self.is_existing_local_path(file_key):
            self._client.delete_object(Bucket=self.settings.s3_bucket_name, Key=file_key)
            return
        Path(file_key).unlink(missing_ok=True)

    @contextmanager
    def download_to_temp(self, file_key: str) -> Iterator[Path]:
        if self.is_existing_local_path(file_key):
            yield Path(file_key)
            return
        with TemporaryDirectory(prefix="pbl6-video-") as directory:
            path = Path(directory) / Path(file_key).name
            self._client.download_file(
                self.settings.s3_bucket_name,
                file_key,
                str(path),
            )
            yield path

    def get_stream_url(self, file_key: str, *, public: bool) -> str:
        if not self.is_s3:
            raise ValueError("URL stream chỉ khả dụng với storage S3")
        if public and self.settings.s3_public_domain.strip():
            return (
                self.settings.s3_public_domain.rstrip("/")
                + "/"
                + file_key.lstrip("/")
            )
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.s3_bucket_name, "Key": file_key},
            ExpiresIn=self.settings.s3_presigned_url_expire_seconds,
        )

    def get_thumbnail_url(self, file_key: str) -> str | None:
        thumbnail_keys = [
            file_key,
            str(Path(file_key).with_suffix(".png")),
            str(Path(file_key).with_suffix(".webp")),
        ]
        if self.is_s3:
            for key in thumbnail_keys:
                try:
                    self._client.head_object(
                        Bucket=self.settings.s3_bucket_name,
                        Key=key,
                    )
                except ClientError as exc:
                    error_code = exc.response.get("Error", {}).get("Code")
                    if error_code in {"403", "404", "NoSuchKey", "NotFound"}:
                        continue
                    raise
                return self.get_stream_url(key, public=True)
            return f"/api/v1/videos/{Path(file_key).stem}/thumbnail"
        for key in thumbnail_keys:
            path = Path(self.settings.upload_dir) / key
            if path.is_file():
                return f"/api/v1/videos/{path.stem}/thumbnail?v={path.stat().st_mtime_ns}"
        return f"/api/v1/videos/{Path(file_key).stem}/thumbnail"

    @staticmethod
    def is_existing_local_path(file_key: str) -> bool:
        return Path(file_key).is_file()


@lru_cache
def get_storage_service() -> StorageService:
    return StorageService()
