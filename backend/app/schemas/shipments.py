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
