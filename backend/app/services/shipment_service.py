import math
import uuid

from sqlalchemy.orm import Session

from app.repositories.shipments import ShipmentRepository
from app.schemas.shipments import ShipmentItem, ShipmentPage


class ShipmentService:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.repository = ShipmentRepository(session, company_id)

    def list(self, search: str | None, page: int, page_size: int) -> ShipmentPage:
        shipments, total = self.repository.list(search, (page - 1) * page_size, page_size)
        items = []
        for shipment in shipments:
            container = shipment.containers[0] if shipment.containers else None
            bill = shipment.bills_of_lading[0] if shipment.bills_of_lading else None
            items.append(
                ShipmentItem(
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
                    teu=container.teu if container else None,
                    revenue=shipment.revenue,
                    currency=shipment.currency,
                    status=shipment.status,
                )
            )
        return ShipmentPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
        )
