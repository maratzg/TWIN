import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class BillOfLadingContainer(BaseModel):
    id: uuid.UUID
    container_number: str
    size_type: str | None
    seal_number: str | None
    package_count: int | None
    package_type: str | None
    gross_weight: Decimal | None
    teu: Decimal | None
    source_document_id: uuid.UUID | None
    source_candidate_group: str | None


class BillOfLadingResponse(BaseModel):
    id: uuid.UUID
    number: str
    source_document_id: uuid.UUID | None
    shipment_id: uuid.UUID
    shipment_reference: str | None
    issue_date: date | None
    carrier: str | None
    shipper: str | None
    shipper_supplier_id: uuid.UUID | None
    consignee: str | None
    consignee_customer_id: uuid.UUID | None
    notify_party: str | None
    vessel: str | None
    voyage: str | None
    port_of_loading: str | None
    port_of_discharge: str | None
    description_of_goods: str | None
    total_packages: int | None
    total_gross_weight: Decimal | None
    measurement: Decimal | None
    measurement_unit: str | None
    containers: list[BillOfLadingContainer]
    created_at: datetime


class BillOfLadingPage(BaseModel):
    items: list[BillOfLadingResponse]
    total: int
    page: int
    page_size: int
    pages: int
