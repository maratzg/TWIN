import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MappingItem(BaseModel):
    source_column: str
    canonical_field: str | None
    confidence: float = Field(ge=0, le=1)
    mapping_method: str
    user_confirmed: bool = False
    sample_values: list[str] = Field(default_factory=list)


class MappingUpdateItem(BaseModel):
    source_column: str
    canonical_field: str | None
    user_confirmed: bool = True


class MappingUpdate(BaseModel):
    mappings: list[MappingUpdateItem]
    reprocess: bool = False


class ImportJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    source_type: str
    selected_sheet: str | None
    sheet_names: list[str]
    header_row: int
    status: str
    detected_row_count: int
    ready_count: int
    imported_count: int
    review_count: int
    rejected_count: int
    created_at: datetime
    committed_at: datetime | None


class ImportAnalysis(ImportJobSummary):
    columns: list[MappingItem]


class ImportHistoryPage(BaseModel):
    items: list[ImportJobSummary]
    total: int
    page: int
    page_size: int
    pages: int


class ImportDetail(ImportJobSummary):
    company_name: str
    mapping_complete: bool
    validation_complete: bool
    mappings: list[MappingItem]
    canonical_fields: list[str]


class MappingResponse(BaseModel):
    import_id: uuid.UUID
    canonical_fields: list[str]
    mappings: list[MappingItem]


class ValidationIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID | None = None
    row_id: uuid.UUID | None = Field(default=None, validation_alias="import_row_id")
    row: int | None = Field(validation_alias="row_number")
    field: str | None
    severity: str
    code: str
    message: str


class ValidationSummary(BaseModel):
    import_id: uuid.UUID
    status: str
    ready: int
    needs_review: int
    invalid: int
    committed: int
    issues: list[ValidationIssueResponse]


class ImportRowListItem(BaseModel):
    id: uuid.UUID
    row_number: int
    disposition: str
    summary: dict[str, Any]
    issue_codes: list[str]
    issue_count: int
    correction_count: int
    approved_at: datetime | None
    committed_at: datetime | None


class ImportRowPage(BaseModel):
    items: list[ImportRowListItem]
    total: int
    page: int
    page_size: int
    pages: int


class ImportCell(BaseModel):
    source_column: str | None
    raw_value: Any = None
    canonical_field: str | None
    system_normalized_value: Any = None
    normalized_value: Any = None
    status: str
    issues: list[ValidationIssueResponse]


class CorrectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    correction_type: str
    source_column: str | None
    canonical_field: str | None
    previous_value: Any = None
    corrected_value: Any = None
    unit: str | None
    reason: str | None
    reviewer_reference: str | None
    created_at: datetime


class ImportRowDetail(BaseModel):
    id: uuid.UUID
    row_number: int
    disposition: str
    raw_data: dict[str, Any]
    system_normalized_data: dict[str, Any] | None
    normalized_data: dict[str, Any] | None
    approved_at: datetime | None
    approved_by: str | None
    committed_at: datetime | None
    canonical_record_id: uuid.UUID | None
    cells: list[ImportCell]
    issues: list[ValidationIssueResponse]
    corrections: list[CorrectionResponse]
    canonical_fields: list[str]


class RowCorrectionRequest(BaseModel):
    source_column: str | None = None
    canonical_field: str
    corrected_value: Any
    unit: str | None = None
    reason: str | None = None


class RowSelectionRequest(BaseModel):
    row_ids: list[uuid.UUID] = Field(default_factory=list)


class BulkActionSummary(BaseModel):
    requested: int
    approved: int
    skipped: list[dict[str, Any]]


class SelectiveCommitRequest(BaseModel):
    row_ids: list[uuid.UUID] | None = None


class CommitSummary(BaseModel):
    import_id: uuid.UUID
    status: str
    requested: int
    committed: int
    skipped: list[dict[str, Any]]
    ready: int
    needs_review: int
    invalid: int
    total_committed: int
    # Compatibility fields used by the Milestone 1 wizard.
    imported: int
    rejected: int


class DataQualitySummary(BaseModel):
    ready_rows: int
    review_rows: int
    invalid_rows: int
    total_evaluated_rows: int
    ready_percent: float
    review_percent: float
    invalid_percent: float
    unresolved_issues: int
    imports_requiring_review: int
    recent_successful_imports: int
    recent_failed_imports: int
