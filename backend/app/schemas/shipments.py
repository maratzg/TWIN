import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ShipmentItem(BaseModel):
    id: uuid.UUID
    reference: str | None
    booking_reference: str | None
    customer: str | None
    bill_of_lading: str | None
    container: str | None
    vessel: str | None
    voyage: str | None
    port_of_loading: str | None
    port_of_discharge: str | None
    etd: date | None
    eta: date | None
    gross_weight: Decimal | None
    teu: Decimal | None
    revenue: Decimal | None
    currency: str | None
    status: str | None


class ShipmentPage(BaseModel):
    items: list[ShipmentItem]
    total: int
    page: int
    page_size: int
    pages: int


class ShipmentDocumentReference(BaseModel):
    id: uuid.UUID
    document_type: str
    number: str
    source_document_id: uuid.UUID | None


class ShipmentContainerDetail(BaseModel):
    id: uuid.UUID
    container_number: str
    size_type: str | None
    seal_number: str | None
    package_count: int | None
    package_type: str | None
    gross_weight: Decimal | None
    teu: Decimal | None
    source_document_id: uuid.UUID | None


class ShipmentInvoiceReference(BaseModel):
    id: uuid.UUID
    invoice_number: str
    direction: str
    total: Decimal
    currency: str
    source_document_id: uuid.UUID | None


class ShipmentDetail(ShipmentItem):
    documents: list[ShipmentDocumentReference]
    containers: list[ShipmentContainerDetail]
    invoices: list[ShipmentInvoiceReference]
