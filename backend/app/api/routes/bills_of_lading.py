import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentCompany, DatabaseSession
from app.schemas.bills_of_lading import BillOfLadingPage, BillOfLadingResponse
from app.services.bill_of_lading_service import BillOfLadingService


router = APIRouter(prefix="/bills-of-lading", tags=["bills-of-lading"])


@router.get("", response_model=BillOfLadingPage)
def list_bills_of_lading(
    session: DatabaseSession,
    company: CurrentCompany,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BillOfLadingPage:
    return BillOfLadingPage(**BillOfLadingService(session, company.id).history(search, page, page_size))


@router.get("/{bill_id}", response_model=BillOfLadingResponse)
def get_bill_of_lading(
    bill_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> BillOfLadingResponse:
    try:
        return BillOfLadingResponse(**BillOfLadingService(session, company.id).detail(bill_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
