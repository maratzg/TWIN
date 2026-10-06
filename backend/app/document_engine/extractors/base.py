from typing import Protocol

from app.document_engine.types import ExtractedCandidate, ExtractedPage


class DocumentExtractor(Protocol):
    document_type: str
    version: str

    def extract(self, pages: list[ExtractedPage]) -> list[ExtractedCandidate]: ...
