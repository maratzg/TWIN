import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentCompany, DatabaseSession
from app.schemas.shipments import ShipmentDetail, ShipmentPage
from app.services.shipment_service import ShipmentService


router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.get("", response_model=ShipmentPage)
def list_shipments(
    session: DatabaseSession,
    company: CurrentCompany,
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ShipmentPage:
    return ShipmentService(session, company.id).list(search, page, page_size)


@router.get("/{shipment_id}", response_model=ShipmentDetail)
def get_shipment(
    shipment_id: uuid.UUID,
    session: DatabaseSession,
    company: CurrentCompany,
) -> ShipmentDetail:
    try:
        return ShipmentService(session, company.id).detail(shipment_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
