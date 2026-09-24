import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import BillOfLading, Container, Customer, Shipment, Voyage


class ShipmentRepository:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id

    def exists_by_identity(self, field: str, value: str) -> bool:
        if field == "shipment_reference":
            statement = select(Shipment.id).where(
                Shipment.company_id == self.company_id,
                Shipment.external_reference == value,
            )
        elif field == "booking_reference":
            statement = select(Shipment.id).where(
                Shipment.company_id == self.company_id,
                Shipment.booking_reference == value,
            )
        elif field == "bill_of_lading_number":
            statement = select(BillOfLading.id).where(
                BillOfLading.company_id == self.company_id,
                BillOfLading.number == value,
            )
        else:
            statement = select(Container.id).where(
                Container.company_id == self.company_id,
                Container.container_number == value,
            )
        return self.session.scalar(statement.limit(1)) is not None

    def list(self, search: str | None, offset: int, limit: int) -> tuple[list[Shipment], int]:
        filters = [Shipment.company_id == self.company_id]
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Shipment.external_reference.ilike(pattern),
                    Shipment.booking_reference.ilike(pattern),
                    Shipment.customer.has(Customer.name.ilike(pattern)),
                    Shipment.bills_of_lading.any(BillOfLading.number.ilike(pattern)),
                    Shipment.containers.any(Container.container_number.ilike(pattern)),
                )
            )
        total = self.session.scalar(select(func.count(Shipment.id)).where(*filters)) or 0
        statement = (
            select(Shipment)
            .where(*filters)
            .options(
                selectinload(Shipment.customer),
                selectinload(Shipment.voyage).selectinload(Voyage.vessel),
                selectinload(Shipment.origin_port),
                selectinload(Shipment.destination_port),
                selectinload(Shipment.containers),
                selectinload(Shipment.bills_of_lading),
            )
            .order_by(Shipment.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(statement).all()), total
