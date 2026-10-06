import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    source_document_id: uuid.UUID | None
    invoice_number: str
    direction: str
    invoice_date: date
    due_date: date | None
    subtotal: Decimal
    vat: Decimal
    total: Decimal
    currency: str
    status: str
    customer_id: uuid.UUID | None
    customer_name: str | None
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    shipment_id: uuid.UUID | None
    created_at: datetime


class InvoiceHistoryPage(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int
    pages: int

