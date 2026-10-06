from pathlib import Path
from typing import Protocol

from app.document_engine.types import ExtractedPage


class OCRUnavailableError(RuntimeError):
    pass


class OCRProvider(Protocol):
    @property
    def available(self) -> bool: ...
    def extract(self, pdf_path: Path) -> list[ExtractedPage]: ...


class UnavailableOCRProvider:
    @property
    def available(self) -> bool:
        return False

    def extract(self, pdf_path: Path) -> list[ExtractedPage]:
        raise OCRUnavailableError(
            "This PDF has no usable embedded text and no local OCR provider is configured."
        )
