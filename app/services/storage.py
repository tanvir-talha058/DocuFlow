import os
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol

from app.config import settings


class StorageBackend(Protocol):
    def save(self, filename: str, fileobj: BinaryIO) -> str:
        """Persist the file, return a stored_path identifier usable by `open_for_read`."""
        ...

    def open_for_read(self, stored_path: str) -> BinaryIO:
        """Return a readable binary file-like object for the stored path."""
        ...


class LocalFilesystemStorage:
    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.upload_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, fileobj: BinaryIO) -> str:
        safe_name = f"{uuid.uuid4()}_{os.path.basename(filename)}"
        dest = self.root / safe_name
        with open(dest, "wb") as out:
            for chunk in iter(lambda: fileobj.read(1024 * 1024), b""):
                out.write(chunk)
        return str(dest)

    def open_for_read(self, stored_path: str) -> BinaryIO:
        return open(stored_path, "rb")


def get_storage() -> StorageBackend:
    return LocalFilesystemStorage()
