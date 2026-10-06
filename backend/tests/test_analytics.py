from datetime import date
from decimal import Decimal
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.analytics.comparisons import compare_values
from app.analytics.metrics import MetricCalculator
from app.analytics.query import AnalyticsFilters
from app.analytics.service import AnalyticsService
from app.analytics.time import Period
from app.api.deps import get_current_company
from app.database import get_db
from app.main import app
from app.models import Base, Company, Customer, Shipment
from app.analytics.demo import populate_demo_company


@pytest.fixture(scope="module")
def analytics_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        first = Company(
            id=uuid.uuid4(),
            name="Analytics Company",
            slug="analytics-company",
            default_currency="EUR",
        )
        second = Company(
            id=uuid.uuid4(),
            name="Isolated Company",
            slug="isolated-company",
            default_currency="USD",
        )
        session.add_all([first, second])
        session.flush()
        result = populate_demo_company(session, first, reset=False)
        yield session, first, second, result
    Base.metadata.drop_all(engine)


def metric_map(response: dict) -> dict[str, dict]:
    return {item["metric"]["key"]: item for item in response["metrics"]}


def test_demo_loader_and_numerical_reconciliation(analytics_database) -> None:
    session, company, _, result = analytics_database
    assert result["shipments"] == 1500
    assert result["containers"] == 2184
    service = AnalyticsService(session, company)
    period = service.resolve_period(None, None)
    facts = service.repository.shipment_facts(period.from_date, period.to_date, AnalyticsFilters())
    response = service.summary(None, None, "EUR", AnalyticsFilters())
    metrics = metric_map(response)

    expected_revenue = sum(
        (item.revenue for item in facts if item.currency == "EUR" and item.revenue is not None),
        Decimal("0"),
    )
    expected_cost = sum(
        (item.cost("EUR") or Decimal("0") for item in facts if item.cost("EUR") is not None),
        Decimal("0"),
    )
    complete = [
        item
        for item in facts
        if item.currency == "EUR" and item.revenue is not None and item.cost("EUR") is not None
    ]
    expected_profit = sum(
        (item.revenue - (item.cost("EUR") or Decimal("0")) for item in complete),
        Decimal("0"),
    )
    expected_teu = sum((item.teu for item in facts), Decimal("0"))
    expected_weight = sum(
        (item.gross_weight for item in facts if item.gross_weight is not None), Decimal("0")
    )
    assert metrics["revenue"]["value"] == expected_revenue
    assert metrics["cost"]["value"] == expected_cost
    assert metrics["contribution_profit"]["value"] == expected_profit
    assert metrics["teu"]["value"] == expected_teu
    assert metrics["gross_weight"]["value"] == expected_weight
    assert metrics["cost"]["coverage"]["percent"] < 100
    assert metrics["teu"]["coverage"]["percent"] < 100
    assert metrics["revenue"]["coverage"]["currency_exclusions"]["USD"] > 0


def test_ratio_container_and_zero_denominator_metrics(analytics_database) -> None:
    session, company, _, _ = analytics_database
    service = AnalyticsService(session, company)
    response = metric_map(
        service.summary(
            None,
            None,
            "EUR",
            AnalyticsFilters(),
            [
                "contribution_margin",
                "revenue_per_shipment",
                "cost_per_shipment",
                "profit_per_shipment",
                "revenue_per_teu",
                "cost_per_teu",
                "profit_per_teu",
                "loaded_containers",
                "empty_containers",
                "loaded_empty_ratio",
            ],
        )
    )
    for key, numerator, denominator in (
        ("revenue_per_shipment", "revenue", "shipments"),
        ("cost_per_shipment", "cost", "shipments"),
        ("profit_per_shipment", "profit", "shipments"),
        ("revenue_per_teu", "revenue", "teu"),
        ("cost_per_teu", "cost", "teu"),
        ("profit_per_teu", "profit", "teu"),
    ):
        components = response[key]["components"]
        assert response[key]["value"] == components[numerator] / Decimal(components[denominator])
    margin = response["contribution_margin"]
    assert margin["value"] == margin["components"]["profit"] / margin["components"]["revenue"] * 100
    loaded = response["loaded_containers"]["components"]["loaded"]
    empty = response["empty_containers"]["components"]["empty"]
    assert loaded > 0 and empty > 0
    assert response["loaded_empty_ratio"]["value"] == Decimal(loaded) / Decimal(empty)

    empty_period = Period(date(2026, 1, 1), date(2026, 1, 31))
    calculator = MetricCalculator()
    for key in (
        "contribution_margin",
        "revenue_per_shipment",
        "cost_per_shipment",
        "profit_per_shipment",
        "revenue_per_teu",
        "cost_per_teu",
        "profit_per_teu",
        "loaded_empty_ratio",
        "average_invoice_value",
        "average_payment_delay",
        "customer_concentration",
        "route_concentration",
    ):
        assert calculator.calculate(key, [], [], empty_period, "EUR").value is None


def test_time_dimension_aggregation_and_comparison(analytics_database) -> None:
    session, company, _, _ = analytics_database
    service = AnalyticsService(session, company)
    summary = metric_map(service.summary(None, None, "EUR", AnalyticsFilters()))
    series = service.timeseries(
        ["revenue", "teu"], None, None, "month", "EUR", AnalyticsFilters()
    )
    assert sum((point["values"]["revenue"] or Decimal("0") for point in series["points"]), Decimal("0")) == summary["revenue"]["value"]
    assert sum((point["values"]["teu"] or Decimal("0") for point in series["points"]), Decimal("0")) == summary["teu"]["value"]
    breakdown = service.breakdown(
        ["revenue", "cost", "contribution_profit", "teu"],
        "route",
        None,
        None,
        "EUR",
        AnalyticsFilters(),
        "revenue",
        "desc",
        1,
        100,
    )
    assert sum((row["values"]["revenue"] or Decimal("0") for row in breakdown["rows"]), Decimal("0")) == summary["revenue"]["value"]
    assert sum((row["values"]["cost"] or Decimal("0") for row in breakdown["rows"]), Decimal("0")) == summary["cost"]["value"]
    assert sum((row["values"]["contribution_profit"] or Decimal("0") for row in breakdown["rows"]), Decimal("0")) == summary["contribution_profit"]["value"]
    assert any(row["comparisons"]["revenue"]["previous"] is not None for row in breakdown["rows"])
    assert compare_values(Decimal("10"), Decimal("0"), "currency")["percentage_change"] is None
    margin_change = compare_values(Decimal("13.2"), Decimal("18.7"), "percent")
    assert margin_change["absolute_change"] == Decimal("-5.5")
    assert margin_change["change_type"] == "percentage_points"


def test_all_time_grains_dimensions_and_combined_filters(analytics_database) -> None:
    session, company, _, _ = analytics_database
    service = AnalyticsService(session, company)
    totals = metric_map(service.summary(None, None, "EUR", AnalyticsFilters()))
    for grain in ("day", "week", "month", "quarter", "year"):
        series = service.timeseries(["teu"], None, None, grain, "EUR", AnalyticsFilters())
        assert sum((point["values"]["teu"] or Decimal("0") for point in series["points"]), Decimal("0")) == totals["teu"]["value"]
    for dimension in ("customer", "route", "pol", "pod", "vessel", "voyage"):
        breakdown = service.breakdown(
            ["teu"], dimension, None, None, "EUR", AnalyticsFilters(), "teu", "desc", 1, 100
        )
        assert sum((row["values"]["teu"] or Decimal("0") for row in breakdown["rows"]), Decimal("0")) == totals["teu"]["value"]

    period = service.resolve_period(None, None)
    all_facts = service.repository.shipment_facts(period.from_date, period.to_date, AnalyticsFilters())
    fact = next(
        item for item in all_facts
        if item.customer_id and item.origin_port_id and item.destination_port_id and item.vessel_id and item.voyage_id
    )
    filters = AnalyticsFilters(
        customer_id=fact.customer_id,
        route=fact.route_key,
        pol_id=fact.origin_port_id,
        pod_id=fact.destination_port_id,
        vessel_id=fact.vessel_id,
        voyage_id=fact.voyage_id,
    )
    filtered_facts = service.repository.shipment_facts(period.from_date, period.to_date, filters)
    filtered_count = metric_map(service.summary(None, None, "EUR", filters, ["shipments"]))["shipments"]["value"]
    assert filtered_facts
    assert filtered_count == Decimal(len(filtered_facts))
    assert all(item.customer_id == fact.customer_id and item.route_key == fact.route_key and item.voyage_id == fact.voyage_id for item in filtered_facts)


def test_invoice_payment_and_receivable_metrics(analytics_database) -> None:
    session, company, _, _ = analytics_database
    service = AnalyticsService(session, company)
    period = service.resolve_period(None, None)
    invoices = service.repository.invoice_facts(period.to_date, AnalyticsFilters())
    response = metric_map(
        service.summary(
            None,
            None,
            "EUR",
            AnalyticsFilters(),
            [
                "invoice_value",
                "average_invoice_value",
                "outstanding_receivables",
                "outstanding_payables",
                "average_payment_delay",
            ],
        )
    )
    receivables = [
        item
        for item in invoices
        if item.direction == "receivable"
        and item.currency == "EUR"
        and period.from_date <= item.invoice_date <= period.to_date
    ]
    expected_invoice_value = sum((item.total for item in receivables), Decimal("0"))
    expected_outstanding = sum(
        (
            item.balance(period.to_date, "EUR") or Decimal("0")
            for item in invoices
            if item.direction == "receivable" and item.currency == "EUR"
        ),
        Decimal("0"),
    )
    delays = []
    for item in receivables:
        final_date = item.final_payment_date(period.to_date, "EUR")
        if item.due_date and final_date:
            delays.append((final_date - item.due_date).days)
    assert response["invoice_value"]["value"] == expected_invoice_value
    assert response["average_invoice_value"]["value"] == expected_invoice_value / len(receivables)
    assert response["outstanding_receivables"]["value"] == expected_outstanding
    assert response["average_payment_delay"]["value"] == Decimal(sum(delays)) / len(delays)
    assert response["outstanding_payables"]["value"] > 0
    payable_outstanding = sum(
        (
            item.balance(period.to_date, "EUR") or Decimal("0")
            for item in invoices
            if item.direction == "payable" and item.currency == "EUR"
        ),
        Decimal("0"),
    )
    assert response["outstanding_payables"]["value"] == payable_outstanding


def test_expected_insights_deduplicate_and_suppress_small_samples(analytics_database) -> None:
    session, company, _, _ = analytics_database
    service = AnalyticsService(session, company)
    response = service.insights(
        None,
        None,
        "EUR",
        AnalyticsFilters(),
        "trailing_3_months",
        30,
    )
    types = {item["type"] for item in response["insights"]}
    assert {
        "margin_deterioration",
        "cost_increase",
        "customer_concentration",
        "payment_deterioration",
        "volume_anomaly",
        "expensive_shipment_anomaly",
        "revenue_growth_margin_decline",
        "customer_profitability_improvement",
    }.issubset(types)
    route_story = next(
        item
        for item in response["insights"]
        if item["type"] == "margin_deterioration" and item["entity_label"] == "Riga → Rotterdam"
    )
    assert route_story["current_value"] < route_story["baseline_value"]
    assert any(item["metric"] == "cost_per_teu" for item in route_story["contributors"])
    assert not any(
        item["type"] == "cost_increase" and item["entity_id"] == route_story["entity_id"]
        for item in response["insights"]
    )
    assert any(
        item["type"] == "customer_profitability_improvement"
        and item["entity_label"] == "Aurora Components"
        for item in response["insights"]
    )


def test_insufficient_sample_suppresses_concentration_and_anomalies(analytics_database) -> None:
    session, _, _, _ = analytics_database
    company = Company(
        id=uuid.uuid4(),
        name="Tiny Analytics Company",
        slug=f"tiny-analytics-{uuid.uuid4()}",
        default_currency="EUR",
    )
    customer = Customer(
        id=uuid.uuid4(),
        company_id=company.id,
        name="Only Customer",
        external_reference="ONLY",
        country_code="LV",
        currency="EUR",
    )
    session.add_all([company, customer])
    session.flush()
    session.add(
        Shipment(
            id=uuid.uuid4(),
            company_id=company.id,
            customer_id=customer.id,
            voyage_id=None,
            origin_port_id=None,
            destination_port_id=None,
            import_job_id=None,
            source_row_number=None,
            external_reference="TINY-1",
            booking_reference=None,
            source_system_reference=None,
            etd=date(2026, 9, 1),
            eta=None,
            status="complete",
            gross_weight=Decimal("100.000"),
            revenue=Decimal("1000.00"),
            currency="EUR",
        )
    )
    session.commit()
    types = {
        item["type"]
        for item in AnalyticsService(session, company).insights(
            date(2026, 9, 1), date(2026, 9, 30), "EUR", AnalyticsFilters(), "trailing_4_weeks", 30
        )["insights"]
    }
    assert "customer_concentration" not in types
    assert "route_concentration" not in types
    assert "expensive_shipment_anomaly" not in types


def test_drilldown_reconciles_and_retains_provenance(analytics_database) -> None:
    session, company, _, _ = analytics_database
    service = AnalyticsService(session, company)
    breakdown = service.breakdown(
        ["revenue"],
        "route",
        None,
        None,
        "EUR",
        AnalyticsFilters(),
        "revenue",
        "desc",
        1,
        100,
    )
    route = breakdown["rows"][0]
    drilldown = service.drilldown(
        "revenue",
        None,
        None,
        "EUR",
        AnalyticsFilters(),
        "route",
        route["dimension_id"],
        1,
        1000,
    )
    assert drilldown["total"] == len(drilldown["items"])
    assert sum((item["revenue"] or Decimal("0") for item in drilldown["items"]), Decimal("0")) == drilldown["reconciled_value"]
    assert drilldown["reconciled_value"] == route["values"]["revenue"]
    assert all(item["shipment_id"] and item["import_job_id"] and item["source_row_number"] for item in drilldown["items"])
    receivables = service.drilldown(
        "outstanding_receivables", None, None, "EUR", AnalyticsFilters(), None, None, 1, 10000
    )
    assert sum((item["outstanding"] or Decimal("0") for item in receivables["items"]), Decimal("0")) == receivables["reconciled_value"]


def test_tenant_isolation_and_analytics_api(analytics_database) -> None:
    session, company, second, _ = analytics_database
    second_shipment = Shipment(
        id=uuid.uuid4(),
        company_id=second.id,
        customer_id=None,
        voyage_id=None,
        origin_port_id=None,
        destination_port_id=None,
        import_job_id=None,
        source_row_number=None,
        external_reference="ISOLATED-1",
        booking_reference="ISOLATED-BOOKING",
        source_system_reference=None,
        etd=date(2026, 9, 1),
        eta=None,
        status="complete",
        gross_weight=Decimal("999999.000"),
        revenue=Decimal("9999999.99"),
        currency="USD",
    )
    session.add(second_shipment)
    session.commit()
    first_revenue = metric_map(
        AnalyticsService(session, company).summary(None, None, "EUR", AnalyticsFilters())
    )["revenue"]["value"]
    second_revenue = metric_map(
        AnalyticsService(session, second).summary(None, None, "USD", AnalyticsFilters())
    )["revenue"]["value"]
    assert second_revenue == Decimal("9999999.99")
    assert first_revenue != second_revenue

    def database_override():
        yield session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_company] = lambda: company
    try:
        client = TestClient(app)
        assert client.get("/api/v1/analytics/metrics").status_code == 200
        summary = client.get("/api/v1/analytics/summary")
        assert summary.status_code == 200
        assert len(summary.json()["metrics"]) == 8
        assert client.get("/api/v1/analytics/timeseries?metrics=revenue,teu&grain=month").status_code == 200
        assert client.get("/api/v1/analytics/breakdown?dimension=customer&page_size=10").status_code == 200
        insights = client.get("/api/v1/analytics/insights?limit=12")
        assert insights.status_code == 200
        assert insights.json()["insights"]
        first_route = client.get("/api/v1/analytics/breakdown?dimension=route&page_size=1").json()["rows"][0]
        drilldown = client.get(
            "/api/v1/analytics/drilldown",
            params={
                "metric": "revenue",
                "dimension": "route",
                "dimension_id": first_route["dimension_id"],
            },
        )
        assert drilldown.status_code == 200
        assert drilldown.json()["items"]
    finally:
        app.dependency_overrides.clear()
