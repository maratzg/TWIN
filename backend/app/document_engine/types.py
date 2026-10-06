from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    blocks: list[dict[str, Any]] = field(default_factory=list)
    extraction_method: str = "embedded_text"


@dataclass(frozen=True)
class ClassificationResult:
    document_type: str
    confidence: float
    method: str
    signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExtractedCandidate:
    field_name: str
    raw_value: str | None
    normalized_value: Any
    confidence: float
    extraction_method: str
    page_number: int | None
    evidence: str | None
    bounding_box: dict[str, float] | None = None
    group_type: str = "document"
    group_index: int = 0


@dataclass(frozen=True)
class ValidationFinding:
    field: str | None
    severity: str
    code: str
    message: str
    group_type: str = "document"
    group_index: int = 0
