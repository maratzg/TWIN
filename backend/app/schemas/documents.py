import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    status: str
    document_type: str
    classification_confidence: float
    classification_method: str | None
    classification_signals: list[str]
    extraction_version: str | None
    extraction_method: str | None
    page_count: int
    field_count: int
    review_count: int
    error_count: int
    approved_at: datetime | None
    approved_by: str | None
    committed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentSummary(DocumentRecord):
    ready_fields: int = 0
    review_fields: int = 0
    error_fields: int = 0
    canonical_invoice_id: uuid.UUID | None = None
    canonical_invoice_number: str | None = None
    canonical_bill_of_lading_id: uuid.UUID | None = None
    canonical_bill_of_lading_number: str | None = None


class DocumentHistoryPage(BaseModel):
    items: list[DocumentSummary]
    total: int
    page: int
    page_size: int
    pages: int


class DocumentPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    page_number: int
    text: str
    blocks: list[dict[str, Any]]
    extraction_method: str
    char_count: int


class FieldCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field_name: str
    group_type: str
    group_index: int
    raw_value: str | None
    system_normalized_value: Any = None
    normalized_value: Any = None
    confidence: float
    extraction_method: str
    page_number: int | None
    evidence: str | None
    bounding_box: dict[str, float] | None
    status: str
    matched_entity_type: str | None
    matched_entity_id: uuid.UUID | None
    match_method: str | None
    match_confidence: float | None


class DocumentIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field: str | None
    severity: str
    code: str
    message: str


class DocumentCorrectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field_name: str
    previous_value: Any = None
    corrected_value: Any = None
    reason: str | None
    reviewer_reference: str | None
    created_at: datetime


class CanonicalInvoiceReference(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str
    direction: str
    status: str


class CanonicalBillOfLadingReference(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str
    shipment_id: uuid.UUID
    source_document_id: uuid.UUID | None


class DocumentDetail(BaseModel):
    document: DocumentRecord
    pages: list[DocumentPageResponse]
    candidates: list[FieldCandidateResponse]
    issues: list[DocumentIssueResponse]
    corrections: list[DocumentCorrectionResponse]
    canonical_invoice: CanonicalInvoiceReference | None
    canonical_bill_of_lading: CanonicalBillOfLadingReference | None
    canonical_fields: list[str]


class ClassificationUpdate(BaseModel):
    document_type: str
    reviewer_reference: str = Field(default="demo-reviewer", max_length=200)


class FieldCorrectionRequest(BaseModel):
    corrected_value: Any
    reason: str | None = None
    reviewer_reference: str = Field(default="demo-reviewer", max_length=200)


class ApprovalRequest(BaseModel):
    reviewer_reference: str = Field(default="demo-reviewer", max_length=200)


class DocumentCommitResponse(BaseModel):
    document: DocumentRecord
    invoice: CanonicalInvoiceReference | None = None
    bill_of_lading: CanonicalBillOfLadingReference | None = None
