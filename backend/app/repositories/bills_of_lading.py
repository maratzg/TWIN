import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import BillOfLading, Shipment, Voyage


class BillOfLadingRepository:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id

    @staticmethod
    def _options():
        return (
            selectinload(BillOfLading.shipment).selectinload(Shipment.containers),
            selectinload(BillOfLading.shipment).selectinload(Shipment.origin_port),
            selectinload(BillOfLading.shipment).selectinload(Shipment.destination_port),
            selectinload(BillOfLading.shipment).selectinload(Shipment.voyage).selectinload(Voyage.vessel),
            selectinload(BillOfLading.shipper_supplier),
            selectinload(BillOfLading.consignee_customer),
        )

    def get(self, bill_id: uuid.UUID) -> BillOfLading | None:
        return self.session.scalar(
            select(BillOfLading)
            .where(BillOfLading.id == bill_id, BillOfLading.company_id == self.company_id)
            .options(*self._options())
        )

    def list(self, search: str | None, offset: int, limit: int) -> tuple[list[BillOfLading], int]:
        filters = [BillOfLading.company_id == self.company_id]
        if search:
            pattern = f"%{search.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(BillOfLading.number).like(pattern),
                    func.lower(BillOfLading.shipper).like(pattern),
                    func.lower(BillOfLading.consignee).like(pattern),
                    func.lower(BillOfLading.carrier).like(pattern),
                )
            )
        total = self.session.scalar(select(func.count(BillOfLading.id)).where(*filters)) or 0
        records = list(
            self.session.scalars(
                select(BillOfLading)
                .where(*filters)
                .options(*self._options())
                .order_by(BillOfLading.issue_date.desc(), BillOfLading.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        return records, total
