import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentCompany, DatabaseSession
from app.config import get_settings
from app.schemas.documents import (
    ApprovalRequest,
    ClassificationUpdate,
    DocumentCommitResponse,
    DocumentDetail,
    DocumentHistoryPage,
    DocumentIssueResponse,
    DocumentRecord,
    DocumentSummary,
    FieldCorrectionRequest,
)
from app.services.document_service import DocumentService, DocumentStateError, DocumentUploadError


router = APIRouter(prefix="/documents", tags=["documents"])
settings = get_settings()


def _service(session: DatabaseSession, company: CurrentCompany) -> DocumentService:
    return DocumentService(session, company.id)


def _detail(service: DocumentService, document_id: uuid.UUID) -> DocumentDetail:
    return DocumentDetail.model_validate(service.detail(document_id))


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, DocumentUploadError):
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    if isinstance(exc, DocumentStateError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=DocumentHistoryPage)
def list_documents(
    session: DatabaseSession,
    company: CurrentCompany,
    search: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    document_type: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentHistoryPage:
    result = _service(session, company).history(
        search=search,
        status=status_filter,
        document_type=document_type,
        page=page,
        page_size=page_size,
    )
    return DocumentHistoryPage(
        **{
            **result,
            "items": [
                DocumentSummary(
                    **DocumentRecord.model_validate(item["document"]).model_dump(),
                    ready_fields=item["ready_fields"],
                    review_fields=item["review_fields"],
                    error_fields=item["error_fields"],
                    canonical_invoice_id=item["canonical_invoice_id"],
                    canonical_invoice_number=item["canonical_invoice_number"],
                    canonical_bill_of_lading_id=item["canonical_bill_of_lading_id"],
                    canonical_bill_of_lading_number=item["canonical_bill_of_lading_number"],
                )
                for item in result["items"]
            ],
        }
    )


@router.post("", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
async def create_document(
    session: DatabaseSession,
    company: CurrentCompany,
    file: UploadFile = File(...),
) -> DocumentDetail:
    content = await file.read(settings.document_max_upload_bytes + 1)
    try:
        service = _service(session, company)
        document = service.upload(file.filename or "upload.pdf", file.content_type, content)
        return _detail(service, document.id)
    except (LookupError, ValueError, OSError) as exc:
        _handle_error(exc)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> DocumentDetail:
    try:
        service = _service(session, company)
        return _detail(service, document_id)
    except LookupError as exc:
        _handle_error(exc)


@router.get("/{document_id}/source")
def get_document_source(
    document_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
    inline: bool = True,
) -> FileResponse:
    try:
        service = _service(session, company)
        document = service.get(document_id)
        path = service.source_path(document_id)
    except (LookupError, OSError) as exc:
        _handle_error(exc)
    disposition = "inline" if inline else "attachment"
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.original_filename,
        content_disposition_type=disposition,
    )


@router.patch("/{document_id}/classification", response_model=DocumentDetail)
def update_classification(
    document_id: uuid.UUID,
    body: ClassificationUpdate,
    session: DatabaseSession,
    company: CurrentCompany,
) -> DocumentDetail:
    try:
        service = _service(session, company)
        service.confirm_classification(document_id, body.document_type, body.reviewer_reference)
        return _detail(service, document_id)
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.patch("/{document_id}/fields/{field_name}", response_model=DocumentDetail)
def correct_field(
    document_id: uuid.UUID,
    field_name: str,
    body: FieldCorrectionRequest,
    session: DatabaseSession,
    company: CurrentCompany,
) -> DocumentDetail:
    try:
        service = _service(session, company)
        service.correct_field(
            document_id,
            field_name,
            body.corrected_value,
            reason=body.reason,
            reviewer_reference=body.reviewer_reference,
        )
        return _detail(service, document_id)
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.patch("/{document_id}/candidates/{candidate_id}", response_model=DocumentDetail)
def correct_candidate(
    document_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: FieldCorrectionRequest,
    session: DatabaseSession,
    company: CurrentCompany,
) -> DocumentDetail:
    try:
        service = _service(session, company)
        service.correct_candidate(
            document_id,
            candidate_id,
            body.corrected_value,
            reason=body.reason,
            reviewer_reference=body.reviewer_reference,
        )
        return _detail(service, document_id)
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post("/{document_id}/revalidate", response_model=DocumentDetail)
def revalidate_document(
    document_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> DocumentDetail:
    try:
        service = _service(session, company)
        service.validate(document_id)
        return _detail(service, document_id)
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post("/{document_id}/approve", response_model=DocumentDetail)
def approve_document(
    document_id: uuid.UUID,
    body: ApprovalRequest,
    session: DatabaseSession,
    company: CurrentCompany,
) -> DocumentDetail:
    try:
        service = _service(session, company)
        service.approve(document_id, body.reviewer_reference)
        return _detail(service, document_id)
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.post("/{document_id}/commit", response_model=DocumentCommitResponse)
def commit_document(
    document_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> DocumentCommitResponse:
    try:
        document, canonical = _service(session, company).commit(document_id)
        if document.document_type == "INVOICE":
            return DocumentCommitResponse(document=document, invoice=canonical)
        return DocumentCommitResponse(document=document, bill_of_lading=canonical)
    except (LookupError, ValueError) as exc:
        _handle_error(exc)


@router.get("/{document_id}/issues", response_model=list[DocumentIssueResponse])
def list_document_issues(
    document_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> list[DocumentIssueResponse]:
    try:
        return [DocumentIssueResponse.model_validate(issue) for issue in _service(session, company).issues(document_id)]
    except LookupError as exc:
        _handle_error(exc)
