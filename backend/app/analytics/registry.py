from dataclasses import asdict, dataclass


ALL_DIMENSIONS = ("time", "customer", "route", "pol", "pod", "vessel", "voyage")
INVOICE_DIMENSIONS = ("time", "customer", "route", "pol", "pod", "vessel", "voyage")


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    display_name: str
    description: str
    unit: str
    calculation: str
    supported_dimensions: tuple[str, ...]
    date_basis: str
    aggregation: str
    decimals: int = 2

    def response(self) -> dict:
        value = asdict(self)
        value["supported_dimensions"] = list(self.supported_dimensions)
        return value


def _metric(
    key: str,
    display_name: str,
    description: str,
    unit: str,
    calculation: str,
    *,
    dimensions: tuple[str, ...] = ALL_DIMENSIONS,
    date_basis: str = "shipment_etd",
    aggregation: str = "sum",
    decimals: int = 2,
) -> MetricDefinition:
    return MetricDefinition(
        key=key,
        display_name=display_name,
        description=description,
        unit=unit,
        calculation=calculation,
        supported_dimensions=dimensions,
        date_basis=date_basis,
        aggregation=aggregation,
        decimals=decimals,
    )


METRICS = {
    definition.key: definition
    for definition in [
        _metric("revenue", "Revenue", "Recorded shipment revenue in the selected currency.", "currency", "sum(shipment.revenue)"),
        _metric("cost", "Attributable cost", "Recorded costs directly linked to shipments.", "currency", "sum(shipment-attributable cost)"),
        _metric("contribution_profit", "Contribution profit", "Shipment revenue less recorded attributable cost.", "currency", "revenue - attributable cost"),
        _metric("contribution_margin", "Contribution margin", "Contribution profit divided by revenue.", "percent", "contribution profit / revenue × 100", aggregation="ratio"),
        _metric("shipments", "Shipments", "Canonical shipments with an operational ETD in the period.", "count", "count(shipments)", decimals=0),
        _metric("containers", "Containers", "Shipment-scoped container occurrences.", "count", "count(containers)", decimals=0),
        _metric("loaded_containers", "Loaded containers", "Containers explicitly marked loaded.", "count", "count(container status=loaded)", decimals=0),
        _metric("empty_containers", "Empty containers", "Containers explicitly marked empty.", "count", "count(container status=empty)", decimals=0),
        _metric("loaded_empty_ratio", "Loaded / empty ratio", "Explicit loaded container count divided by explicit empty count.", "ratio", "loaded containers / empty containers", aggregation="ratio"),
        _metric("teu", "TEU", "Sum of valid canonical container TEU.", "teu", "sum(container.teu)"),
        _metric("gross_weight", "Gross weight", "Sum of canonical shipment gross weight.", "kg", "sum(shipment.gross_weight)", decimals=3),
        _metric("revenue_per_shipment", "Revenue / shipment", "Revenue divided by revenue-bearing shipments.", "currency", "revenue / revenue-bearing shipments", aggregation="ratio"),
        _metric("cost_per_shipment", "Cost / shipment", "Attributable cost divided by cost-bearing shipments.", "currency", "cost / cost-bearing shipments", aggregation="ratio"),
        _metric("profit_per_shipment", "Profit / shipment", "Contribution profit divided by in-scope shipments.", "currency", "contribution profit / shipments", aggregation="ratio"),
        _metric("revenue_per_teu", "Revenue / TEU", "Revenue divided by valid TEU on revenue-bearing shipments.", "currency_per_teu", "revenue / revenue-bearing TEU", aggregation="ratio"),
        _metric("cost_per_teu", "Cost / TEU", "Attributable cost divided by valid TEU on cost-bearing shipments.", "currency_per_teu", "cost / cost-bearing TEU", aggregation="ratio"),
        _metric("profit_per_teu", "Profit / TEU", "Contribution profit divided by valid TEU on financially represented shipments.", "currency_per_teu", "contribution profit / finance-bearing TEU", aggregation="ratio"),
        _metric("invoice_value", "Invoice value", "Receivable invoice total in the selected currency.", "currency", "sum(receivable invoice total)", dimensions=INVOICE_DIMENSIONS, date_basis="invoice_date"),
        _metric("average_invoice_value", "Average invoice value", "Average receivable invoice total.", "currency", "invoice value / receivable invoices", dimensions=INVOICE_DIMENSIONS, date_basis="invoice_date", aggregation="ratio"),
        _metric("outstanding_receivables", "Outstanding receivables", "Unpaid receivable invoice balance as of period end.", "currency", "sum(max(invoice total - payments, 0))", dimensions=INVOICE_DIMENSIONS, date_basis="as_of_period_end"),
        _metric("outstanding_payables", "Outstanding payables", "Unpaid payable invoice balance as of period end.", "currency", "sum(max(invoice total - payments, 0))", dimensions=INVOICE_DIMENSIONS, date_basis="as_of_period_end"),
        _metric("average_payment_delay", "Average payment delay", "Average days from due date to final payment for fully paid receivables.", "days", "average(final payment date - due date)", dimensions=INVOICE_DIMENSIONS, date_basis="invoice_date", aggregation="average", decimals=1),
        _metric("customer_concentration", "Customer concentration", "Largest named customer's share of revenue.", "percent", "largest customer revenue / revenue × 100", aggregation="ratio"),
        _metric("route_concentration", "Route concentration", "Largest canonical route's share of valid TEU.", "percent", "largest route TEU / TEU × 100", aggregation="ratio"),
    ]
}


SUMMARY_METRICS = (
    "revenue",
    "cost",
    "contribution_profit",
    "contribution_margin",
    "shipments",
    "containers",
    "teu",
    "gross_weight",
)


def metric_definition(key: str) -> MetricDefinition:
    try:
        return METRICS[key]
    except KeyError as exc:
        raise ValueError(f"Unknown metric: {key}") from exc
