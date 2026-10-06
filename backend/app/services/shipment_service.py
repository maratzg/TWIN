import math
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invoice
from app.repositories.shipments import ShipmentRepository
from app.schemas.shipments import ShipmentDetail, ShipmentItem, ShipmentPage


class ShipmentService:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id
        self.repository = ShipmentRepository(session, company_id)

    def list(self, search: str | None, page: int, page_size: int) -> ShipmentPage:
        shipments, total = self.repository.list(search, (page - 1) * page_size, page_size)
        items = [self._item(shipment) for shipment in shipments]
        return ShipmentPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
        )

    def detail(self, shipment_id: uuid.UUID) -> ShipmentDetail:
        shipment = self.repository.get(shipment_id)
        if shipment is None:
            raise LookupError("Shipment not found.")
        item = self._item(shipment)
        invoices = list(
            self.session.scalars(
                select(Invoice).where(
                    Invoice.company_id == self.company_id,
                    Invoice.shipment_id == shipment.id,
                )
            ).all()
        )
        return ShipmentDetail(
            **item.model_dump(),
            documents=[
                {
                    "id": bill.id,
                    "document_type": "BILL_OF_LADING",
                    "number": bill.number,
                    "source_document_id": bill.source_document_id,
                }
                for bill in shipment.bills_of_lading
            ],
            containers=[
                {
                    "id": container.id,
                    "container_number": container.container_number,
                    "size_type": container.size_type,
                    "seal_number": container.seal_number,
                    "package_count": container.package_count,
                    "package_type": container.package_type,
                    "gross_weight": container.gross_weight,
                    "teu": container.teu,
                    "source_document_id": container.source_document_id,
                }
                for container in shipment.containers
            ],
            invoices=[
                {
                    "id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "direction": invoice.direction,
                    "total": invoice.total,
                    "currency": invoice.currency,
                    "source_document_id": invoice.source_document_id,
                }
                for invoice in invoices
            ],
        )

    @staticmethod
    def _item(shipment) -> ShipmentItem:
        container = shipment.containers[0] if shipment.containers else None
        bill = shipment.bills_of_lading[0] if shipment.bills_of_lading else None
        return ShipmentItem(
            id=shipment.id,
            reference=shipment.external_reference,
            booking_reference=shipment.booking_reference,
            customer=shipment.customer.name if shipment.customer else None,
            bill_of_lading=bill.number if bill else None,
            container=container.container_number if container else None,
            vessel=shipment.voyage.vessel.name if shipment.voyage and shipment.voyage.vessel else None,
            voyage=shipment.voyage.voyage_number if shipment.voyage else None,
            port_of_loading=shipment.origin_port.name if shipment.origin_port else None,
            port_of_discharge=shipment.destination_port.name if shipment.destination_port else None,
            etd=shipment.etd,
            eta=shipment.eta,
            gross_weight=shipment.gross_weight,
            teu=sum((item.teu or 0 for item in shipment.containers), 0) or None,
            revenue=shipment.revenue,
            currency=shipment.currency,
            status=shipment.status,
        )
