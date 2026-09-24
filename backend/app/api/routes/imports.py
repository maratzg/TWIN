import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentCompany, DatabaseSession
from app.models import ImportJob
from app.schemas.imports import (
    BulkActionSummary,
    CommitSummary,
    ImportAnalysis,
    ImportDetail,
    ImportHistoryPage,
    ImportJobSummary,
    ImportRowDetail,
    ImportRowListItem,
    ImportRowPage,
    MappingItem,
    MappingResponse,
    MappingUpdate,
    RowCorrectionRequest,
    RowSelectionRequest,
    SelectiveCommitRequest,
    ValidationIssueResponse,
    ValidationSummary,
)
from app.services.import_service import ImportService, ImportStateError
from app.services.review_service import ImportReviewService


router = APIRouter(prefix="/imports", tags=["imports"])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _service(session: DatabaseSession, company: CurrentCompany) -> ImportService:
    return ImportService(session, company.id)


def _review_service(session: DatabaseSession, company: CurrentCompany) -> ImportReviewService:
    return ImportReviewService(session, company.id)


def _mapping_item(column) -> MappingItem:
    return MappingItem(
        source_column=column.source_column,
        canonical_field=column.canonical_field,
        confidence=column.confidence,
        mapping_method=column.mapping_method,
        user_confirmed=column.user_confirmed,
        sample_values=column.sample_values,
    )


def _analysis(job: ImportJob) -> ImportAnalysis:
    summary = ImportJobSummary.model_validate(job).model_dump()
    return ImportAnalysis(**summary, columns=[_mapping_item(column) for column in job.columns])


def _validation_summary(service: ImportService, job: ImportJob) -> ValidationSummary:
    return ValidationSummary(
        import_id=job.id,
        status=job.status,
        ready=job.ready_count,
        needs_review=job.review_count,
        invalid=job.rejected_count,
        committed=job.imported_count,
        issues=[ValidationIssueResponse.model_validate(issue) for issue in service.issues(job.id)],
    )


def _row_detail(data: dict) -> ImportRowDetail:
    row = data["row"]
    return ImportRowDetail(
        id=row.id,
        row_number=row.row_number,
        disposition=row.disposition,
        raw_data=row.raw_data,
        system_normalized_data=row.system_normalized_data,
        normalized_data=row.normalized_data,
        approved_at=row.approved_at,
        approved_by=row.approved_by,
        committed_at=row.committed_at,
        canonical_record_id=row.canonical_record_id,
        cells=data["cells"],
        issues=[ValidationIssueResponse.model_validate(issue) for issue in data["issues"]],
        corrections=data["corrections"],
        canonical_fields=data["canonical_fields"],
    )


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ImportStateError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=ImportHistoryPage)
def list_imports(
    session: DatabaseSession,
    company: CurrentCompany,
    search: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ImportHistoryPage:
    result = _review_service(session, company).history(
        search=search,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return ImportHistoryPage(**result)


@router.post("", response_model=ImportAnalysis, status_code=status.HTTP_201_CREATED)
async def create_import(
    session: DatabaseSession,
    company: CurrentCompany,
    file: UploadFile = File(...),
) -> ImportAnalysis:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 20 MB upload limit.")
    try:
        return _analysis(_service(session, company).analyze(file.filename or "upload", content))
    except (ValueError, OSError) as exc:
        _handle_error(exc)


@router.get("/{import_id}", response_model=ImportDetail)
def get_import(
    import_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> ImportDetail:
    try:
        data = _review_service(session, company).detail(import_id)
    except LookupError as exc:
        _handle_error(exc)
    job = data["job"]
    summary = ImportJobSummary.model_validate(job).model_dump()
    return ImportDetail(
        **summary,
        company_name=data["company_name"],
        mapping_complete=data["mapping_complete"],
        validation_complete=data["validation_complete"],
        mappings=[_mapping_item(column) for column in job.columns],
        canonical_fields=data["canonical_fields"],
    )


@router.get("/{import_id}/mapping", response_model=MappingResponse)
def get_mapping(
    import_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> MappingResponse:
    service = _service(session, company)
    try:
        job = service.get(import_id)
    except LookupError as exc:
        _handle_error(exc)
    return MappingResponse(
        import_id=job.id,
        canonical_fields=service.mapper.canonical_fields,
        mappings=[_mapping_item(column) for column in job.columns],
    )


@router.put("/{import_id}/mapping", response_model=MappingResponse)
def update_mapping(
    import_id: uuid.UUID,
    body: MappingUpdate,
    session: DatabaseSession,
    company: CurrentCompany,
) -> MappingResponse:
    service = _service(session, company)
    try:
        job = service.update_mapping(
            import_id,
            [item.model_dump() for item in body.mappings],
            reprocess=body.reprocess,
        )
    except (LookupError, ValueError) as exc:
        _handle_error(exc)
    return MappingResponse(
        import_id=job.id,
        canonical_fields=service.mapper.canonical_fields,
        mappings=[_mapping_item(column) for column in job.columns],
    )


@router.post("/{import_id}/validate", response_model=ValidationSummary)
@router.post("/{import_id}/revalidate", response_model=ValidationSummary)
def validate_import(
    import_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> ValidationSummary:
    service = _service(session, company)
    try:
        service.validate(import_id)
        job = service.get(import_id)
    except (LookupError, ValueError) as exc:
        _handle_error(exc)
    return _validation_summary(service, job)


@router.get("/{import_id}/rows", response_model=ImportRowPage)
def list_import_rows(
    import_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
    disposition: str | None = None,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ImportRowPage:
    try:
        result = _review_service(session, company).rows(
            import_id,
            disposition="review" if disposition == "needs_review" else disposition,
            search=search,
            page=page,
            page_size=page_size,
        )
    except LookupError as exc:
        _handle_error(exc)
    items = [
        ImportRowListItem(
            id=item["row"].id,
            row_number=item["row"].row_number,
            disposition=item["row"].disposition,
            summary=item["summary"],
            issue_codes=item["issue_codes"],
            issue_count=item["issue_count"],
            correction_count=item["correction_count"],
            approved_at=item["row"].approved_at,
            committed_at=item["row"].committed_at,
        )
        for item in result["items"]
    ]
    return ImportRowPage(**{**result, "items": items})


@router.get("/{import_id}/rows/{row_id}", response_model=ImportRowDetail)
def get_import_row(
    import_id: uuid.UUID,
    row_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> ImportRowDetail:
    try:
        return _row_detail(_review_service(session, company).row_detail(import_id, row_id))
    except LookupError as exc:
        _handle_error(exc)


@router.patch("/{import_id}/rows/{row_id}", response_model=ImportRowDetail)
def correct_import_row(
    import_id: uuid.UUID,
    row_id: uuid.UUID,
    body: RowCorrectionRequest,
    session: DatabaseSession,
    company: CurrentCompany,
) -> ImportRowDetail:
    service = _service(session, company)
    try:
        service.correct_row(
            import_id,
            row_id,
            body.canonical_field,
            body.corrected_value,
            source_column=body.source_column,
            unit=body.unit,
            reason=body.reason,
        )
        return _row_detail(_review_service(session, company).row_detail(import_id, row_id))
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post("/{import_id}/rows/{row_id}/revalidate", response_model=ImportRowDetail)
def revalidate_import_row(
    import_id: uuid.UUID,
    row_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> ImportRowDetail:
    service = _service(session, company)
    try:
        service._row(import_id, row_id)
        service.validate(import_id)
        return _row_detail(_review_service(session, company).row_detail(import_id, row_id))
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post("/{import_id}/revalidate-rows", response_model=ValidationSummary)
def revalidate_selected_rows(
    import_id: uuid.UUID,
    body: RowSelectionRequest,
    session: DatabaseSession,
    company: CurrentCompany,
) -> ValidationSummary:
    service = _service(session, company)
    try:
        service._selected_rows(service.get(import_id), body.row_ids)
        service.validate(import_id)
        job = service.get(import_id)
        return _validation_summary(service, job)
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post("/{import_id}/approve", response_model=BulkActionSummary)
def approve_import_rows(
    import_id: uuid.UUID,
    body: RowSelectionRequest,
    session: DatabaseSession,
    company: CurrentCompany,
) -> BulkActionSummary:
    try:
        return BulkActionSummary(**_service(session, company).approve_rows(import_id, body.row_ids))
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.get("/{import_id}/issues", response_model=list[ValidationIssueResponse])
def get_issues(
    import_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> list[ValidationIssueResponse]:
    try:
        return [
            ValidationIssueResponse.model_validate(issue)
            for issue in _service(session, company).issues(import_id)
        ]
    except LookupError as exc:
        _handle_error(exc)


@router.post("/{import_id}/commit", response_model=CommitSummary)
def commit_import(
    import_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
    body: SelectiveCommitRequest | None = None,
) -> CommitSummary:
    try:
        result = _service(session, company).commit_rows(
            import_id,
            body.row_ids if body else None,
        )
    except (LookupError, ValueError) as exc:
        _handle_error(exc)
    return CommitSummary(
        **result,
        imported=result["committed"],
        rejected=result["invalid"],
    )
