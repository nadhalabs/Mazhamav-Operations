from abc import ABC, abstractmethod
from pathlib import Path
import boto3
from app.core.config import get_settings


class MediaStorage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get(self, key: str) -> tuple[bytes, str]: ...


class LocalMediaStorage(MediaStorage):
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid media key")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key); path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(data); temporary.replace(path)

    def get(self, key: str) -> tuple[bytes, str]:
        return self._path(key).read_bytes(), "image/png"


class S3MediaStorage(MediaStorage):
    def __init__(self):
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.client = boto3.client("s3", region_name=settings.s3_region, endpoint_url=settings.s3_endpoint_url, aws_access_key_id=settings.s3_access_key_id, aws_secret_access_key=settings.s3_secret_access_key)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type, ServerSideEncryption="AES256", CacheControl="private, max-age=300")

    def get(self, key: str) -> tuple[bytes, str]:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read(), response.get("ContentType", "application/octet-stream")


def get_media_storage() -> MediaStorage:
    settings = get_settings()
    return S3MediaStorage() if settings.media_storage_backend == "s3" else LocalMediaStorage(settings.media_local_path)
