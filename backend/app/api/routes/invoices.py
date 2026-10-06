import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentCompany, DatabaseSession
from app.schemas.invoices import InvoiceHistoryPage, InvoiceResponse
from app.services.invoice_service import InvoiceService


router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("", response_model=InvoiceHistoryPage)
def list_invoices(
    session: DatabaseSession,
    company: CurrentCompany,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InvoiceHistoryPage:
    return InvoiceHistoryPage(
        **InvoiceService(session, company.id).history(
            search=search,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> InvoiceResponse:
    try:
        return InvoiceResponse(**InvoiceService(session, company.id).detail(invoice_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

