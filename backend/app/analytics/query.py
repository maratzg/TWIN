from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models import (
    BillOfLading,
    Container,
    Cost,
    Customer,
    Invoice,
    Payment,
    Port,
    Shipment,
    Supplier,
    Vessel,
    Voyage,
)


@dataclass(frozen=True)
class AnalyticsFilters:
    customer_id: uuid.UUID | None = None
    route: str | None = None
    pol_id: uuid.UUID | None = None
    pod_id: uuid.UUID | None = None
    vessel_id: uuid.UUID | None = None
    voyage_id: uuid.UUID | None = None

    def response(self) -> dict[str, str | None]:
        return {
            "customer_id": str(self.customer_id) if self.customer_id else None,
            "route": self.route,
            "pol_id": str(self.pol_id) if self.pol_id else None,
            "pod_id": str(self.pod_id) if self.pod_id else None,
            "vessel_id": str(self.vessel_id) if self.vessel_id else None,
            "voyage_id": str(self.voyage_id) if self.voyage_id else None,
        }


@dataclass(frozen=True)
class ContainerComponent:
    id: uuid.UUID
    teu: Decimal | None
    gross_weight: Decimal | None
    status: str | None
    source_document_id: uuid.UUID | None


@dataclass(frozen=True)
class CostComponent:
    id: uuid.UUID
    amount: Decimal
    currency: str
    cost_date: date
    supplier_id: uuid.UUID | None


@dataclass
class ShipmentFact:
    id: uuid.UUID
    operational_date: date
    reference: str | None
    customer_id: uuid.UUID | None
    customer_name: str | None
    origin_port_id: uuid.UUID | None
    origin_port_name: str | None
    destination_port_id: uuid.UUID | None
    destination_port_name: str | None
    vessel_id: uuid.UUID | None
    vessel_name: str | None
    voyage_id: uuid.UUID | None
    voyage_number: str | None
    revenue: Decimal | None
    currency: str | None
    gross_weight: Decimal | None
    import_job_id: uuid.UUID | None
    source_row_number: int | None
    containers: list[ContainerComponent] = field(default_factory=list)
    costs: list[CostComponent] = field(default_factory=list)
    source_document_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def route_key(self) -> str:
        if self.origin_port_id and self.destination_port_id:
            return f"{self.origin_port_id}:{self.destination_port_id}"
        return "unresolved"

    @property
    def route_label(self) -> str:
        if self.origin_port_name and self.destination_port_name:
            return f"{self.origin_port_name} → {self.destination_port_name}"
        return "Unresolved route"

    @property
    def teu(self) -> Decimal:
        return sum((item.teu for item in self.containers if item.teu is not None), Decimal("0"))

    @property
    def valid_teu_containers(self) -> int:
        return sum(1 for item in self.containers if item.teu is not None)

    def cost(self, currency: str) -> Decimal | None:
        values = [item.amount for item in self.costs if item.currency == currency]
        return sum(values, Decimal("0")) if values else None

    def dimension(self, name: str) -> tuple[str, str]:
        if name == "customer":
            return (str(self.customer_id), self.customer_name) if self.customer_id else ("unassigned", "Unassigned customer")
        if name == "route":
            return self.route_key, self.route_label
        if name == "pol":
            return (str(self.origin_port_id), self.origin_port_name) if self.origin_port_id else ("unresolved", "Unresolved POL")
        if name == "pod":
            return (str(self.destination_port_id), self.destination_port_name) if self.destination_port_id else ("unresolved", "Unresolved POD")
        if name == "vessel":
            return (str(self.vessel_id), self.vessel_name) if self.vessel_id else ("unresolved", "Unresolved vessel")
        if name == "voyage":
            label = f"{self.vessel_name or 'Unknown vessel'} / {self.voyage_number}" if self.voyage_number else "Unresolved voyage"
            return (str(self.voyage_id), label) if self.voyage_id else ("unresolved", label)
        return "all", "All records"


@dataclass(frozen=True)
class PaymentComponent:
    id: uuid.UUID
    payment_date: date
    amount: Decimal
    currency: str


@dataclass
class InvoiceFact:
    id: uuid.UUID
    invoice_number: str
    invoice_date: date
    due_date: date | None
    direction: str
    total: Decimal
    currency: str
    customer_id: uuid.UUID | None
    customer_name: str | None
    supplier_id: uuid.UUID | None
    supplier_name: str | None
    shipment_id: uuid.UUID | None
    route_key: str
    route_label: str
    origin_port_id: uuid.UUID | None
    origin_port_name: str | None
    destination_port_id: uuid.UUID | None
    destination_port_name: str | None
    vessel_id: uuid.UUID | None
    vessel_name: str | None
    voyage_id: uuid.UUID | None
    voyage_number: str | None
    source_document_id: uuid.UUID | None
    payments: list[PaymentComponent] = field(default_factory=list)

    def paid(self, as_of: date, currency: str) -> Decimal:
        return sum(
            (payment.amount for payment in self.payments if payment.payment_date <= as_of and payment.currency == currency),
            Decimal("0"),
        )

    def balance(self, as_of: date, currency: str) -> Decimal | None:
        if self.currency != currency or self.invoice_date > as_of:
            return None
        return max(self.total - self.paid(as_of, currency), Decimal("0"))

    def final_payment_date(self, as_of: date, currency: str) -> date | None:
        paid = Decimal("0")
        for payment in sorted(self.payments, key=lambda item: item.payment_date):
            if payment.payment_date > as_of or payment.currency != currency:
                continue
            paid += payment.amount
            if paid >= self.total:
                return payment.payment_date
        return None

    def dimension(self, name: str) -> tuple[str, str]:
        if name == "customer":
            return (str(self.customer_id), self.customer_name) if self.customer_id else ("unassigned", "Unassigned customer")
        if name == "route":
            return self.route_key, self.route_label
        if name == "pol":
            return (str(self.origin_port_id), self.origin_port_name) if self.origin_port_id else ("unresolved", "Unresolved POL")
        if name == "pod":
            return (str(self.destination_port_id), self.destination_port_name) if self.destination_port_id else ("unresolved", "Unresolved POD")
        if name == "vessel":
            return (str(self.vessel_id), self.vessel_name) if self.vessel_id else ("unresolved", "Unresolved vessel")
        if name == "voyage":
            label = f"{self.vessel_name or 'Unknown vessel'} / {self.voyage_number}" if self.voyage_number else "Unresolved voyage"
            return (str(self.voyage_id), label) if self.voyage_id else ("unresolved", label)
        return "all", "All records"


class AnalyticsQueryRepository:
    def __init__(self, session: Session, company_id: uuid.UUID) -> None:
        self.session = session
        self.company_id = company_id

    def latest_date(self) -> date | None:
        shipment_date = self.session.scalar(
            select(func.max(Shipment.etd)).where(Shipment.company_id == self.company_id)
        )
        invoice_date = self.session.scalar(
            select(func.max(Invoice.invoice_date)).where(Invoice.company_id == self.company_id)
        )
        return max((value for value in (shipment_date, invoice_date) if value is not None), default=None)

    def shipment_facts(self, from_date: date, to_date: date, filters: AnalyticsFilters) -> list[ShipmentFact]:
        origin = aliased(Port)
        destination = aliased(Port)
        predicates = self._shipment_predicates(from_date, to_date, filters)
        rows = self.session.execute(
            select(
                Shipment,
                Customer.name,
                origin.name,
                destination.name,
                Voyage.voyage_number,
                Vessel.id,
                Vessel.name,
            )
            .outerjoin(Customer, Customer.id == Shipment.customer_id)
            .outerjoin(origin, origin.id == Shipment.origin_port_id)
            .outerjoin(destination, destination.id == Shipment.destination_port_id)
            .outerjoin(Voyage, Voyage.id == Shipment.voyage_id)
            .outerjoin(Vessel, Vessel.id == Voyage.vessel_id)
            .where(*predicates)
            .order_by(Shipment.etd, Shipment.id)
        ).all()
        facts: dict[uuid.UUID, ShipmentFact] = {}
        for shipment, customer_name, origin_name, destination_name, voyage_number, vessel_id, vessel_name in rows:
            facts[shipment.id] = ShipmentFact(
                id=shipment.id,
                operational_date=shipment.etd,
                reference=shipment.external_reference,
                customer_id=shipment.customer_id,
                customer_name=customer_name,
                origin_port_id=shipment.origin_port_id,
                origin_port_name=origin_name,
                destination_port_id=shipment.destination_port_id,
                destination_port_name=destination_name,
                vessel_id=vessel_id,
                vessel_name=vessel_name,
                voyage_id=shipment.voyage_id,
                voyage_number=voyage_number,
                revenue=shipment.revenue,
                currency=shipment.currency,
                gross_weight=shipment.gross_weight,
                import_job_id=shipment.import_job_id,
                source_row_number=shipment.source_row_number,
            )
        if not facts:
            return []
        for container in self.session.scalars(
            select(Container)
            .join(Shipment, Shipment.id == Container.shipment_id)
            .where(Container.company_id == self.company_id, *predicates)
        ):
            facts[container.shipment_id].containers.append(
                ContainerComponent(
                    id=container.id,
                    teu=container.teu,
                    gross_weight=container.gross_weight,
                    status=container.status,
                    source_document_id=container.source_document_id,
                )
            )
        for cost in self.session.scalars(
            select(Cost)
            .join(Shipment, Shipment.id == Cost.shipment_id)
            .where(Cost.company_id == self.company_id, *predicates)
        ):
            facts[cost.shipment_id].costs.append(
                CostComponent(
                    id=cost.id,
                    amount=cost.amount,
                    currency=cost.currency,
                    cost_date=cost.cost_date,
                    supplier_id=cost.supplier_id,
                )
            )
        document_rows = self.session.execute(
            select(BillOfLading.shipment_id, BillOfLading.source_document_id)
            .join(Shipment, Shipment.id == BillOfLading.shipment_id)
            .where(
                BillOfLading.company_id == self.company_id,
                BillOfLading.source_document_id.is_not(None),
                *predicates,
            )
        ).all()
        for shipment_id, source_document_id in document_rows:
            facts[shipment_id].source_document_ids.append(source_document_id)
        return list(facts.values())

    def invoice_facts(self, to_date: date, filters: AnalyticsFilters) -> list[InvoiceFact]:
        origin = aliased(Port)
        destination = aliased(Port)
        invoice_customer = aliased(Customer)
        predicates = self._invoice_predicates(to_date, filters)
        base = (
            select(
                Invoice,
                invoice_customer.name,
                Supplier.name,
                Shipment.origin_port_id,
                origin.name,
                Shipment.destination_port_id,
                destination.name,
                Shipment.voyage_id,
                Voyage.voyage_number,
                Vessel.id,
                Vessel.name,
            )
            .outerjoin(invoice_customer, invoice_customer.id == Invoice.customer_id)
            .outerjoin(Supplier, Supplier.id == Invoice.supplier_id)
            .outerjoin(Shipment, Shipment.id == Invoice.shipment_id)
            .outerjoin(origin, origin.id == Shipment.origin_port_id)
            .outerjoin(destination, destination.id == Shipment.destination_port_id)
            .outerjoin(Voyage, Voyage.id == Shipment.voyage_id)
            .outerjoin(Vessel, Vessel.id == Voyage.vessel_id)
            .where(*predicates)
        )
        rows = self.session.execute(base.order_by(Invoice.invoice_date, Invoice.id)).all()
        facts: dict[uuid.UUID, InvoiceFact] = {}
        for (
            invoice,
            customer_name,
            supplier_name,
            origin_id,
            origin_name,
            destination_id,
            destination_name,
            voyage_id,
            voyage_number,
            vessel_id,
            vessel_name,
        ) in rows:
            route_key = f"{origin_id}:{destination_id}" if origin_id and destination_id else "unresolved"
            route_label = f"{origin_name} → {destination_name}" if origin_name and destination_name else "Unresolved route"
            facts[invoice.id] = InvoiceFact(
                id=invoice.id,
                invoice_number=invoice.invoice_number,
                invoice_date=invoice.invoice_date,
                due_date=invoice.due_date,
                direction=invoice.direction,
                total=invoice.total,
                currency=invoice.currency,
                customer_id=invoice.customer_id,
                customer_name=customer_name,
                supplier_id=invoice.supplier_id,
                supplier_name=supplier_name,
                shipment_id=invoice.shipment_id,
                route_key=route_key,
                route_label=route_label,
                origin_port_id=origin_id,
                origin_port_name=origin_name,
                destination_port_id=destination_id,
                destination_port_name=destination_name,
                vessel_id=vessel_id,
                vessel_name=vessel_name,
                voyage_id=voyage_id,
                voyage_number=voyage_number,
                source_document_id=invoice.source_document_id,
            )
        if not facts:
            return []
        payment_rows = self.session.execute(
            select(Payment)
            .join(Invoice, Invoice.id == Payment.invoice_id)
            .outerjoin(Shipment, Shipment.id == Invoice.shipment_id)
            .where(Payment.company_id == self.company_id, Payment.payment_date <= to_date, *predicates)
        ).scalars()
        for payment in payment_rows:
            if payment.invoice_id in facts:
                facts[payment.invoice_id].payments.append(
                    PaymentComponent(
                        id=payment.id,
                        payment_date=payment.payment_date,
                        amount=payment.amount,
                        currency=payment.currency,
                    )
                )
        return list(facts.values())

    def options(self) -> dict[str, list[dict[str, str]]]:
        customers = [
            {"id": str(identifier), "label": name}
            for identifier, name in self.session.execute(
                select(Customer.id, Customer.name)
                .where(Customer.company_id == self.company_id)
                .order_by(Customer.name)
            )
        ]
        ports = [
            {"id": str(identifier), "label": name}
            for identifier, name in self.session.execute(
                select(Port.id, Port.name)
                .where(Port.company_id == self.company_id)
                .order_by(Port.name)
            )
        ]
        vessels = [
            {"id": str(identifier), "label": name}
            for identifier, name in self.session.execute(
                select(Vessel.id, Vessel.name)
                .where(Vessel.company_id == self.company_id)
                .order_by(Vessel.name)
            )
        ]
        voyages = [
            {"id": str(identifier), "label": f"{vessel_name or 'Unknown vessel'} / {number}"}
            for identifier, number, vessel_name in self.session.execute(
                select(Voyage.id, Voyage.voyage_number, Vessel.name)
                .outerjoin(Vessel, Vessel.id == Voyage.vessel_id)
                .where(Voyage.company_id == self.company_id)
                .order_by(Voyage.voyage_number)
            )
        ]
        origin = aliased(Port)
        destination = aliased(Port)
        routes = [
            {"id": f"{origin_id}:{destination_id}", "label": f"{origin_name} → {destination_name}"}
            for origin_id, destination_id, origin_name, destination_name in self.session.execute(
                select(
                    Shipment.origin_port_id,
                    Shipment.destination_port_id,
                    origin.name,
                    destination.name,
                )
                .join(origin, origin.id == Shipment.origin_port_id)
                .join(destination, destination.id == Shipment.destination_port_id)
                .where(Shipment.company_id == self.company_id)
                .distinct()
                .order_by(origin.name, destination.name)
            )
        ]
        currency_values = (
            select(Shipment.currency.label("currency"))
            .where(Shipment.company_id == self.company_id, Shipment.currency.is_not(None))
            .union(
                select(Invoice.currency.label("currency")).where(
                    Invoice.company_id == self.company_id
                ),
                select(Cost.currency.label("currency")).where(
                    Cost.company_id == self.company_id
                ),
            )
            .subquery()
        )
        currencies = [
            {"id": value, "label": value}
            for value in self.session.scalars(
                select(currency_values.c.currency)
                .where(currency_values.c.currency.is_not(None))
                .distinct()
                .order_by(currency_values.c.currency)
            )
        ]
        return {
            "customers": customers,
            "routes": routes,
            "ports": ports,
            "vessels": vessels,
            "voyages": voyages,
            "currencies": currencies,
        }

    def _shipment_predicates(
        self, from_date: date, to_date: date, filters: AnalyticsFilters
    ) -> list:
        predicates = [
            Shipment.company_id == self.company_id,
            Shipment.etd.is_not(None),
            Shipment.etd >= from_date,
            Shipment.etd <= to_date,
        ]
        if filters.customer_id:
            predicates.append(Shipment.customer_id == filters.customer_id)
        if filters.pol_id:
            predicates.append(Shipment.origin_port_id == filters.pol_id)
        if filters.pod_id:
            predicates.append(Shipment.destination_port_id == filters.pod_id)
        if filters.voyage_id:
            predicates.append(Shipment.voyage_id == filters.voyage_id)
        if filters.vessel_id:
            predicates.append(
                Shipment.voyage_id.in_(
                    select(Voyage.id).where(
                        Voyage.company_id == self.company_id,
                        Voyage.vessel_id == filters.vessel_id,
                    )
                )
            )
        route = self._parse_route(filters.route)
        if route:
            predicates.extend(
                [Shipment.origin_port_id == route[0], Shipment.destination_port_id == route[1]]
            )
        return predicates

    def _invoice_predicates(self, to_date: date, filters: AnalyticsFilters) -> list:
        predicates = [Invoice.company_id == self.company_id, Invoice.invoice_date <= to_date]
        if filters.customer_id:
            predicates.append(Invoice.customer_id == filters.customer_id)
        if filters.pol_id:
            predicates.append(Shipment.origin_port_id == filters.pol_id)
        if filters.pod_id:
            predicates.append(Shipment.destination_port_id == filters.pod_id)
        if filters.voyage_id:
            predicates.append(Shipment.voyage_id == filters.voyage_id)
        if filters.vessel_id:
            predicates.append(
                Shipment.voyage_id.in_(
                    select(Voyage.id).where(
                        Voyage.company_id == self.company_id,
                        Voyage.vessel_id == filters.vessel_id,
                    )
                )
            )
        route = self._parse_route(filters.route)
        if route:
            predicates.extend(
                [Shipment.origin_port_id == route[0], Shipment.destination_port_id == route[1]]
            )
        return predicates

    @staticmethod
    def _parse_route(value: str | None) -> tuple[uuid.UUID, uuid.UUID] | None:
        if not value:
            return None
        try:
            origin, destination = value.split(":", 1)
            return uuid.UUID(origin), uuid.UUID(destination)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Route must contain canonical origin and destination IDs.") from exc
