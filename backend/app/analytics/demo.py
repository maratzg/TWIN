"""Create a deterministic canonical logistics company for Milestone 4A analytics."""

from argparse import ArgumentParser
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import random
import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    BillOfLading,
    Company,
    Container,
    Cost,
    Customer,
    ImportJob,
    ImportRow,
    Invoice,
    Payment,
    Port,
    Shipment,
    Supplier,
    Vessel,
    Voyage,
)


NAMESPACE = uuid.UUID("c53cb619-a855-47f2-b6bf-4f0bdcb9e73d")
SEED = 420_041
START_MONTH = date(2025, 10, 1)
END_DATE = date(2026, 9, 23)

PORTS = [
    ("LVRIX", "Riga", "LV"),
    ("NLRTM", "Rotterdam", "NL"),
    ("DEHAM", "Hamburg", "DE"),
    ("EETLL", "Tallinn", "EE"),
    ("LTKLJ", "Klaipeda", "LT"),
    ("PLGDN", "Gdansk", "PL"),
    ("SEGOT", "Gothenburg", "SE"),
    ("FIHEL", "Helsinki", "FI"),
    ("BEANR", "Antwerp", "BE"),
    ("DKCPH", "Copenhagen", "DK"),
]

ROUTES = [
    ("LVRIX", "NLRTM"),  # injected margin deterioration
    ("LVRIX", "DEHAM"),
    ("EETLL", "NLRTM"),
    ("LTKLJ", "PLGDN"),
    ("LVRIX", "SEGOT"),  # injected seasonal volume spike
    ("EETLL", "FIHEL"),
    ("LTKLJ", "DEHAM"),
    ("PLGDN", "BEANR"),
    ("SEGOT", "DKCPH"),
    ("FIHEL", "NLRTM"),
]

CUSTOMERS = [
    "Baltic Home Markets",  # injected concentration
    "Northstar Retail Group",  # injected payment deterioration
    "Aurora Components",  # injected profitability improvement
    "Nordic Harvest Foods",
    "Hanseatic Industrial Supply",
    "Rheinland Distribution",
    "Scandia Medical Systems",
    "Benelux Homeware",
    "Tallinn Technical Trading",
    "Klaipeda Timber Partners",
    "Gothenburg Marine Equipment",
    "Finnish Packaging Cooperative",
    "Danish Retail Logistics",
    "Baltic Electronics Group",
    "Amber Foods Europe",
    "Northern Tools AB",
    "Rotterdam Project Cargo",
    "Vilnius Consumer Products",
    "Tartu Manufacturing",
    "Riga Automotive Components",
    "Nordic Furniture Network",
    "European Garden Supply",
    "Blue Coast Wholesale",
    "Central Baltic Pharma",
]

SUPPLIERS = [
    "Twin Ocean Lines",
    "Baltic Port Services",
    "Nordic Haulage SIA",
    "Riga Terminal Operations",
    "Hanseatic Feeder Lines",
    "Scandinavian Customs Services",
    "Benelux Inland Transport",
    "Baltic Equipment Leasing",
]

VESSELS = [
    ("EVER AURORA", "9811001"),
    ("BALTIC HORIZON", "9754321"),
    ("NORDIC STAR", "9682403"),
    ("HANSE EXPLORER", "9777112"),
    ("AMBER SEA", "9730048"),
    ("SCANDIA BRIDGE", "9802256"),
    ("RIGA TRADER", "9718818"),
    ("EUROPA FEEDER", "9665027"),
]


def stable_id(kind: str, value: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{kind}:{value}")


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def weight(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def month_start(value: date, offset: int) -> date:
    absolute = value.year * 12 + value.month - 1 + offset
    year, month_index = divmod(absolute, 12)
    return date(year, month_index + 1, 1)


def month_end(value: date) -> date:
    return month_start(value, 1) - timedelta(days=1)


def reset_company(session: Session, company: Company) -> None:
    import_ids = select(ImportJob.id).where(ImportJob.company_id == company.id)
    session.execute(
        update(ImportRow)
        .where(ImportRow.import_job_id.in_(import_ids))
        .values(canonical_record_id=None)
    )
    for model in (Payment, Invoice, Cost, BillOfLading, Container, Shipment, Voyage, Vessel, Port, Customer, Supplier):
        session.execute(delete(model).where(model.company_id == company.id))
    demo_jobs = list(
        session.scalars(
            select(ImportJob).where(
                ImportJob.company_id == company.id,
                ImportJob.filename.like("analytics-demo-%"),
            )
        ).all()
    )
    for job in demo_jobs:
        session.delete(job)
    session.flush()


def populate_demo_company(session: Session, company: Company, *, reset: bool) -> dict[str, int | str]:
    existing = session.scalar(
        select(Shipment.id).where(Shipment.company_id == company.id).limit(1)
    )
    if existing and not reset:
        raise RuntimeError("The demo company already has canonical data; rerun with reset enabled.")
    if reset:
        reset_company(session, company)
    company.name = "Baltic Freight Demo SIA"
    company.default_currency = "EUR"

    rng = random.Random(SEED)
    port_map: dict[str, Port] = {}
    for code, name, country in PORTS:
        port = Port(
            id=stable_id("port", code),
            company_id=company.id,
            unlocode=code,
            name=name,
            country_code=country,
        )
        port_map[code] = port
        session.add(port)

    customers: list[Customer] = []
    for index, name in enumerate(CUSTOMERS, start=1):
        customer = Customer(
            id=stable_id("customer", name),
            company_id=company.id,
            external_reference=f"BFD-CUST-{index:03d}",
            name=name,
            registration_number=f"REG{index:08d}",
            vat_number=f"LV{40000000000 + index}",
            country_code="LV" if index % 3 else "EE",
            currency="EUR",
        )
        customers.append(customer)
        session.add(customer)

    suppliers: list[Supplier] = []
    for index, name in enumerate(SUPPLIERS, start=1):
        supplier = Supplier(
            id=stable_id("supplier", name),
            company_id=company.id,
            external_reference=f"BFD-SUP-{index:03d}",
            name=name,
            registration_number=f"SUP{index:08d}",
            vat_number=f"LV{50000000000 + index}",
            country_code="LV",
            currency="EUR",
        )
        suppliers.append(supplier)
        session.add(supplier)

    vessels: list[Vessel] = []
    for name, imo in VESSELS:
        vessel = Vessel(
            id=stable_id("vessel", imo),
            company_id=company.id,
            name=name,
            imo_number=imo,
        )
        vessels.append(vessel)
        session.add(vessel)

    voyages: dict[tuple[int, int], Voyage] = {}
    import_jobs: dict[int, ImportJob] = {}
    shipments: list[Shipment] = []
    containers: list[Container] = []
    costs: list[Cost] = []
    invoices: list[Invoice] = []
    payments: list[Payment] = []
    bills: list[BillOfLading] = []
    import_rows: list[ImportRow] = []
    anomaly_indexes = {1112, 1187, 1265, 1379, 1462}
    shipment_index = 0

    for month_index in range(12):
        current_month = month_start(START_MONTH, month_index)
        final_month_day = min(month_end(current_month), END_DATE)
        count = 110 if month_index < 9 else 170
        if current_month.month == 9 and current_month.year == 2026:
            count = 170
        job = ImportJob(
            id=stable_id("import", current_month.isoformat()),
            company_id=company.id,
            filename=f"analytics-demo-{current_month:%Y-%m}.csv",
            source_type="csv",
            selected_sheet=None,
            sheet_names=[],
            header_row=1,
            status="committed",
            detected_row_count=count,
            ready_count=0,
            imported_count=count,
            review_count=0,
            rejected_count=0,
            mapping_snapshot={"origin": "deterministic_analytics_demo_v1"},
            committed_at=datetime.combine(final_month_day, datetime.min.time(), tzinfo=UTC),
        )
        import_jobs[month_index] = job
        session.add(job)
        days = (final_month_day - current_month).days + 1
        for row_number in range(1, count + 1):
            shipment_index += 1
            operational_date = current_month + timedelta(days=rng.randrange(days))
            current_story_period = operational_date >= date(2026, 7, 1)
            route_weights = [18, 12, 10, 8, 9, 8, 9, 8, 8, 10]
            if current_story_period:
                route_weights[0] = 28
                route_weights[4] = 21 if operational_date.month in {7, 8} else 12
            route_index = rng.choices(range(len(ROUTES)), weights=route_weights, k=1)[0]
            origin_code, destination_code = ROUTES[route_index]
            if current_story_period and rng.random() < 0.39:
                customer_index = 0
            elif route_index == 4 and operational_date.month in {7, 8} and rng.random() < 0.48:
                customer_index = 3
            else:
                customer_index = rng.randrange(1, len(customers))
            customer = customers[customer_index]
            vessel = vessels[route_index % len(vessels)]
            voyage_key = (month_index, route_index)
            voyage = voyages.get(voyage_key)
            if voyage is None:
                voyage_number = f"{origin_code[-3:]}{current_month:%y%m}{route_index + 1:02d}"
                voyage = Voyage(
                    id=stable_id("voyage", f"{current_month:%Y-%m}:{route_index}"),
                    company_id=company.id,
                    vessel_id=vessel.id,
                    voyage_number=voyage_number,
                    departure_date=current_month,
                    arrival_date=min(current_month + timedelta(days=12 + route_index), month_end(current_month)),
                )
                voyages[voyage_key] = voyage
                session.add(voyage)

            container_count = rng.choices([1, 2, 3], weights=[60, 35, 5], k=1)[0]
            shipment_teu = Decimal("0")
            shipment_weight = Decimal("0")
            shipment_containers: list[Container] = []
            for position in range(container_count):
                equipment = rng.choices(
                    [("20GP", Decimal("1")), ("40GP", Decimal("2")), ("40HC", Decimal("2"))],
                    weights=[32, 28, 40],
                    k=1,
                )[0]
                valid_teu = rng.random() >= 0.03
                teu = equipment[1] if valid_teu else None
                container_weight = weight(rng.uniform(6500, 17500) * float(equipment[1]))
                status = rng.choices(["loaded", "empty", None], weights=[85, 10, 5], k=1)[0]
                container = Container(
                    id=stable_id("container", f"{shipment_index}:{position}"),
                    company_id=company.id,
                    shipment_id=stable_id("shipment", str(shipment_index)),
                    source_document_id=None,
                    source_candidate_group=None,
                    container_number=f"BFDZ{shipment_index:06d}{position}",
                    size_type=equipment[0] if valid_teu else "40",
                    seal_number=f"BFD-SEAL-{shipment_index:06d}-{position}",
                    package_count=rng.randint(20, 140),
                    package_type="PALLETS",
                    teu=teu,
                    gross_weight=container_weight,
                    status=status,
                )
                shipment_containers.append(container)
                containers.append(container)
                if teu is not None:
                    shipment_teu += teu
                shipment_weight += container_weight

            if shipment_teu == 0:
                pricing_teu = Decimal(str(container_count * 2))
            else:
                pricing_teu = shipment_teu
            base_revenue_per_teu = Decimal(str(1010 + route_index * 24))
            base_cost_per_teu = Decimal(str(730 + route_index * 17))
            if route_index == 0:
                base_revenue_per_teu = Decimal("1070") if current_story_period else Decimal("1050")
                base_cost_per_teu = Decimal("930") if current_story_period else Decimal("820")
            elif current_story_period:
                base_revenue_per_teu *= Decimal("1.07")
                base_cost_per_teu *= Decimal("1.11")
            if customer_index == 0 and current_story_period:
                base_revenue_per_teu *= Decimal("1.08")
            if customer_index == 2 and current_story_period:
                base_cost_per_teu *= Decimal("0.58")
            revenue = money(base_revenue_per_teu * pricing_teu * Decimal(str(rng.uniform(0.94, 1.06))))
            total_cost = money(base_cost_per_teu * pricing_teu * Decimal(str(rng.uniform(0.95, 1.05))))
            if shipment_index in anomaly_indexes:
                total_cost = money(total_cost * Decimal("2.65"))
            shipment_currency = rng.choices(["EUR", "USD", None], weights=[94, 4, 2], k=1)[0]
            shipment_id = stable_id("shipment", str(shipment_index))
            shipment = Shipment(
                id=shipment_id,
                company_id=company.id,
                customer_id=customer.id,
                voyage_id=voyage.id,
                origin_port_id=port_map[origin_code].id,
                destination_port_id=port_map[destination_code].id,
                import_job_id=job.id,
                source_row_number=row_number + 1,
                external_reference=f"BFD-{operational_date:%y%m}-{shipment_index:05d}",
                booking_reference=f"BOOK-{shipment_index:06d}",
                source_system_reference=f"DEMO-{shipment_index:06d}",
                etd=operational_date,
                eta=operational_date + timedelta(days=7 + route_index),
                status="completed" if operational_date < END_DATE - timedelta(days=14) else "in_transit",
                gross_weight=None if rng.random() < 0.035 else shipment_weight,
                revenue=revenue if shipment_currency else None,
                currency=shipment_currency,
            )
            shipments.append(shipment)
            for container in shipment_containers:
                container.shipment_id = shipment.id
            if rng.random() < 0.38:
                bills.append(
                    BillOfLading(
                        id=stable_id("bill", str(shipment_index)),
                        company_id=company.id,
                        shipment_id=shipment.id,
                        source_document_id=None,
                        shipper_supplier_id=suppliers[0].id,
                        consignee_customer_id=customer.id,
                        number=f"BFD-BL-{shipment_index:07d}",
                        issue_date=operational_date - timedelta(days=2),
                        carrier=suppliers[0].name,
                        shipper=company.name,
                        consignee=customer.name,
                        notify_party=customer.name,
                        references=shipment.booking_reference,
                        description_of_goods="Synthetic mixed commercial cargo",
                        total_packages=sum(item.package_count or 0 for item in shipment_containers),
                        total_gross_weight=shipment_weight,
                        measurement=None,
                        measurement_unit=None,
                    )
                )
            has_cost = rng.random() >= 0.08
            if has_cost:
                cost_currency = "USD" if shipment_currency == "EUR" and rng.random() < 0.025 else (shipment_currency or "EUR")
                ocean_amount = money(total_cost * Decimal("0.76"))
                handling_amount = money(total_cost - ocean_amount)
                costs.extend(
                    [
                        Cost(
                            id=stable_id("cost", f"{shipment_index}:ocean"),
                            company_id=company.id,
                            shipment_id=shipment.id,
                            supplier_id=suppliers[0].id,
                            category="ocean_freight",
                            amount=ocean_amount,
                            currency=cost_currency,
                            cost_date=operational_date,
                            external_reference=f"COST-O-{shipment_index:06d}",
                        ),
                        Cost(
                            id=stable_id("cost", f"{shipment_index}:handling"),
                            company_id=company.id,
                            shipment_id=shipment.id,
                            supplier_id=suppliers[1].id,
                            category="terminal_handling",
                            amount=handling_amount,
                            currency=cost_currency,
                            cost_date=operational_date,
                            external_reference=f"COST-H-{shipment_index:06d}",
                        ),
                    ]
                )
            if shipment.revenue is not None and rng.random() < 0.96:
                invoice_id = stable_id("invoice", f"receivable:{shipment_index}")
                invoice_date = operational_date + timedelta(days=1)
                due_date = invoice_date + timedelta(days=30)
                receivable = Invoice(
                    id=invoice_id,
                    company_id=company.id,
                    source_document_id=None,
                    customer_id=customer.id,
                    supplier_id=None,
                    shipment_id=shipment.id,
                    invoice_number=f"BFD-AR-{shipment_index:07d}",
                    direction="receivable",
                    invoice_date=invoice_date,
                    due_date=due_date,
                    subtotal=shipment.revenue,
                    vat=Decimal("0.00"),
                    total=shipment.revenue,
                    currency=shipment.currency,
                    status="issued",
                )
                invoices.append(receivable)
                pay_probability = 0.88 if invoice_date <= END_DATE - timedelta(days=35) else 0.28
                if rng.random() < pay_probability:
                    if customer_index == 1:
                        delay = rng.randint(12, 24) if current_story_period else rng.randint(-2, 4)
                    else:
                        delay = rng.randint(-4, 8)
                    payment_date = due_date + timedelta(days=delay)
                    payments.append(
                        Payment(
                            id=stable_id("payment", f"receivable:{shipment_index}"),
                            company_id=company.id,
                            invoice_id=invoice_id,
                            payment_date=payment_date,
                            amount=shipment.revenue,
                            currency=shipment.currency,
                            external_reference=f"PAY-AR-{shipment_index:07d}",
                        )
                    )
                    receivable.status = "paid"
                elif rng.random() < 0.24:
                    partial = money(shipment.revenue * Decimal("0.45"))
                    payments.append(
                        Payment(
                            id=stable_id("payment", f"receivable-partial:{shipment_index}"),
                            company_id=company.id,
                            invoice_id=invoice_id,
                            payment_date=min(due_date, END_DATE),
                            amount=partial,
                            currency=shipment.currency,
                            external_reference=f"PAY-PART-{shipment_index:07d}",
                        )
                    )
                    receivable.status = "partial"
            if has_cost and shipment_index % 4 == 0:
                payable_id = stable_id("invoice", f"payable:{shipment_index}")
                payable_date = operational_date + timedelta(days=2)
                payable_due = payable_date + timedelta(days=21)
                payable = Invoice(
                    id=payable_id,
                    company_id=company.id,
                    source_document_id=None,
                    customer_id=None,
                    supplier_id=suppliers[0].id,
                    shipment_id=shipment.id,
                    invoice_number=f"BFD-AP-{shipment_index:07d}",
                    direction="payable",
                    invoice_date=payable_date,
                    due_date=payable_due,
                    subtotal=total_cost,
                    vat=Decimal("0.00"),
                    total=total_cost,
                    currency=shipment_currency or "EUR",
                    status="issued",
                )
                invoices.append(payable)
                if payable_due <= END_DATE and rng.random() < 0.83:
                    payments.append(
                        Payment(
                            id=stable_id("payment", f"payable:{shipment_index}"),
                            company_id=company.id,
                            invoice_id=payable_id,
                            payment_date=payable_due + timedelta(days=rng.randint(-3, 6)),
                            amount=total_cost,
                            currency=payable.currency,
                            external_reference=f"PAY-AP-{shipment_index:07d}",
                        )
                    )
                    payable.status = "paid"
            import_rows.append(
                ImportRow(
                    id=stable_id("import-row", str(shipment_index)),
                    import_job_id=job.id,
                    row_number=row_number + 1,
                    raw_data={"shipment_reference": shipment.external_reference, "customer": customer.name},
                    system_normalized_data={"shipment_reference": shipment.external_reference, "customer_name": customer.name},
                    normalized_data={"shipment_reference": shipment.external_reference, "customer_name": customer.name},
                    disposition="committed",
                    last_validated_at=datetime.combine(operational_date, datetime.min.time(), tzinfo=UTC),
                    approved_at=datetime.combine(operational_date, datetime.min.time(), tzinfo=UTC),
                    approved_by="deterministic-demo-loader",
                    committed_at=datetime.combine(operational_date, datetime.min.time(), tzinfo=UTC),
                    canonical_record_id=shipment.id,
                )
            )

    session.add_all(shipments)
    session.add_all(containers)
    session.add_all(costs)
    session.add_all(invoices)
    session.add_all(payments)
    session.add_all(bills)
    session.add_all(import_rows)
    session.commit()
    return {
        "company": company.name,
        "seed": SEED,
        "shipments": len(shipments),
        "containers": len(containers),
        "costs": len(costs),
        "invoices": len(invoices),
        "payments": len(payments),
        "bills_of_lading": len(bills),
        "customers": len(customers),
        "routes": len(ROUTES),
        "vessels": len(vessels),
        "voyages": len(voyages),
    }


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Replace canonical data for the configured demo tenant.")
    args = parser.parse_args()
    settings = get_settings()
    with SessionLocal() as session:
        company = session.scalar(select(Company).where(Company.slug == settings.demo_company_slug))
        if company is None:
            company = Company(
                id=stable_id("company", settings.demo_company_slug),
                name="Baltic Freight Demo SIA",
                slug=settings.demo_company_slug,
                default_currency="EUR",
                registration_number=settings.demo_company_registration_number,
                vat_number=settings.demo_company_vat_number,
            )
            session.add(company)
            session.flush()
        result = populate_demo_company(session, company, reset=args.reset)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
