import os
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Protocol


class DocumentStorage(Protocol):
    def put(self, company_id: uuid.UUID, document_id: uuid.UUID, checksum: str, content: bytes) -> str: ...
    def read(self, storage_key: str) -> bytes: ...
    def path(self, storage_key: str) -> Path: ...


class LocalDocumentStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put(self, company_id: uuid.UUID, document_id: uuid.UUID, checksum: str, content: bytes) -> str:
        storage_key = f"{company_id}/{document_id}/{checksum}.pdf"
        target = self._safe_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=target.parent, prefix="upload-", suffix=".tmp", delete=False) as stream:
            stream.write(content)
            temporary = Path(stream.name)
        os.replace(temporary, target)
        return storage_key

    def read(self, storage_key: str) -> bytes:
        return self._safe_path(storage_key).read_bytes()

    def path(self, storage_key: str) -> Path:
        target = self._safe_path(storage_key)
        if not target.is_file():
            raise FileNotFoundError("Stored document was not found.")
        return target

    def _safe_path(self, storage_key: str) -> Path:
        if Path(storage_key).is_absolute():
            raise ValueError("Absolute storage keys are not allowed.")
        target = (self.root / storage_key).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Storage key escapes the document root.")
        return target
