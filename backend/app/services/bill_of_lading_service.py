import math
import uuid

from sqlalchemy.orm import Session

from app.models import BillOfLading
from app.repositories.bills_of_lading import BillOfLadingRepository


class BillOfLadingService:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.repository = BillOfLadingRepository(session, company_id)

    def history(self, search: str | None, page: int, page_size: int) -> dict:
        bills, total = self.repository.list(search, (page - 1) * page_size, page_size)
        return {
            "items": [self._response(bill) for bill in bills],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        }

    def detail(self, bill_id: uuid.UUID) -> dict:
        bill = self.repository.get(bill_id)
        if bill is None:
            raise LookupError("Bill of Lading not found.")
        return self._response(bill)

    @staticmethod
    def _response(bill: BillOfLading) -> dict:
        shipment = bill.shipment
        voyage = shipment.voyage if shipment else None
        vessel = voyage.vessel if voyage else None
        return {
            "id": bill.id,
            "number": bill.number,
            "source_document_id": bill.source_document_id,
            "shipment_id": bill.shipment_id,
            "shipment_reference": shipment.external_reference if shipment else None,
            "issue_date": bill.issue_date,
            "carrier": bill.carrier,
            "shipper": bill.shipper,
            "shipper_supplier_id": bill.shipper_supplier_id,
            "consignee": bill.consignee,
            "consignee_customer_id": bill.consignee_customer_id,
            "notify_party": bill.notify_party,
            "vessel": vessel.name if vessel else None,
            "voyage": voyage.voyage_number if voyage else None,
            "port_of_loading": shipment.origin_port.name if shipment and shipment.origin_port else None,
            "port_of_discharge": shipment.destination_port.name if shipment and shipment.destination_port else None,
            "description_of_goods": bill.description_of_goods,
            "total_packages": bill.total_packages,
            "total_gross_weight": bill.total_gross_weight,
            "measurement": bill.measurement,
            "measurement_unit": bill.measurement_unit,
            "containers": [
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
                    "source_candidate_group": container.source_candidate_group,
                }
                for container in shipment.containers
            ],
            "created_at": bill.created_at,
        }
