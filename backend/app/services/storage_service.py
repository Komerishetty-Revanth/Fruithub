from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings


class StorageService(ABC):
    """Future: S3StorageService can replace LocalStorageService."""

    @abstractmethod
    def save(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def read(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def url(self, key: str) -> str: ...


class LocalStorageService(StorageService):
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):  # blocks "../" tricks
            raise ValueError("Invalid storage key")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def url(self, key: str) -> str:
        return f"/uploads/{key}"


_storage: StorageService = LocalStorageService(settings.UPLOAD_DIR)


def get_storage() -> StorageService:
    return _storage