from datetime import date, timedelta
from decimal import Decimal
import math
import uuid

from sqlalchemy.orm import Session

from app.analytics.comparisons import compare_values
from app.analytics.insights import InsightEngine
from app.analytics.metrics import MetricCalculator
from app.analytics.query import AnalyticsFilters, AnalyticsQueryRepository, InvoiceFact, ShipmentFact
from app.analytics.registry import ALL_DIMENSIONS, METRICS, SUMMARY_METRICS, metric_definition
from app.analytics.time import GRAINS, Period, iter_buckets, previous_period
from app.models import Company


INVOICE_METRICS = {
    "invoice_value",
    "average_invoice_value",
    "outstanding_receivables",
    "outstanding_payables",
    "average_payment_delay",
}


class AnalyticsService:
    def __init__(self, session: Session, company: Company) -> None:
        self.session = session
        self.company = company
        self.repository = AnalyticsQueryRepository(session, company.id)
        self.calculator = MetricCalculator()

    def registry(self) -> dict:
        return {
            "metrics": [definition.response() for definition in METRICS.values()],
            "time_grains": ["day", "week", "month", "quarter", "year"],
            "dimensions": list(ALL_DIMENSIONS),
        }

    def options(self) -> dict:
        period = self.resolve_period(None, None)
        return {
            "default_period": period.response(),
            "default_currency": self.company.default_currency,
            **self.repository.options(),
        }

    def summary(
        self,
        from_date: date | None,
        to_date: date | None,
        currency: str | None,
        filters: AnalyticsFilters,
        metric_keys: list[str] | None = None,
    ) -> dict:
        period = self.resolve_period(from_date, to_date)
        comparison_period = previous_period(period)
        selected_currency = self._currency(currency)
        keys = metric_keys or list(SUMMARY_METRICS)
        self._validate_metrics(keys)
        current_shipments = self.repository.shipment_facts(period.from_date, period.to_date, filters)
        current_invoices = self.repository.invoice_facts(period.to_date, filters)
        previous_shipments = self.repository.shipment_facts(
            comparison_period.from_date, comparison_period.to_date, filters
        )
        previous_invoices = self.repository.invoice_facts(comparison_period.to_date, filters)
        values = []
        for key in keys:
            current = self.calculator.calculate(
                key, current_shipments, current_invoices, period, selected_currency
            )
            previous = self.calculator.calculate(
                key,
                previous_shipments,
                previous_invoices,
                comparison_period,
                selected_currency,
            )
            definition = metric_definition(key)
            values.append(
                {
                    "metric": definition.response(),
                    "value": current.value,
                    "currency": selected_currency if "currency" in definition.unit else None,
                    "coverage": current.coverage,
                    "comparison": compare_values(current.value, previous.value, definition.unit),
                    "components": current.components,
                }
            )
        return {
            "period": period.response(),
            "comparison_period": comparison_period.response(),
            "currency": selected_currency,
            "filters": filters.response(),
            "metrics": values,
        }

    def timeseries(
        self,
        metric_keys: list[str],
        from_date: date | None,
        to_date: date | None,
        grain: str,
        currency: str | None,
        filters: AnalyticsFilters,
    ) -> dict:
        self._validate_metrics(metric_keys)
        if grain not in GRAINS:
            raise ValueError(f"Unsupported time grain: {grain}")
        period = self.resolve_period(from_date, to_date)
        selected_currency = self._currency(currency)
        shipments = self.repository.shipment_facts(period.from_date, period.to_date, filters)
        invoices = self.repository.invoice_facts(period.to_date, filters)
        points = []
        for bucket in iter_buckets(period, grain):
            bucket_shipments = [
                item for item in shipments if bucket.from_date <= item.operational_date <= bucket.to_date
            ]
            values: dict[str, Decimal | None] = {}
            coverage: dict[str, dict] = {}
            for key in metric_keys:
                result = self.calculator.calculate(
                    key, bucket_shipments, invoices, bucket, selected_currency
                )
                values[key] = result.value
                coverage[key] = result.coverage
            points.append(
                {
                    "period": bucket.response(),
                    "label": self._bucket_label(bucket.from_date, grain),
                    "values": values,
                    "coverage": coverage,
                }
            )
        return {
            "period": period.response(),
            "grain": grain,
            "currency": selected_currency,
            "filters": filters.response(),
            "metrics": [metric_definition(key).response() for key in metric_keys],
            "points": points,
        }

    def breakdown(
        self,
        metric_keys: list[str],
        dimension: str,
        from_date: date | None,
        to_date: date | None,
        currency: str | None,
        filters: AnalyticsFilters,
        sort_by: str | None,
        sort_order: str,
        page: int,
        page_size: int,
    ) -> dict:
        self._validate_metrics(metric_keys)
        if dimension not in ALL_DIMENSIONS or dimension == "time":
            raise ValueError("Breakdown dimension must be customer, route, pol, pod, vessel, or voyage.")
        for key in metric_keys:
            if dimension not in metric_definition(key).supported_dimensions:
                raise ValueError(f"Metric {key} does not support dimension {dimension}.")
        period = self.resolve_period(from_date, to_date)
        comparison_period = previous_period(period)
        selected_currency = self._currency(currency)
        current_shipments = self.repository.shipment_facts(period.from_date, period.to_date, filters)
        current_invoices = self.repository.invoice_facts(period.to_date, filters)
        previous_shipments = self.repository.shipment_facts(
            comparison_period.from_date, comparison_period.to_date, filters
        )
        previous_invoices = self.repository.invoice_facts(comparison_period.to_date, filters)
        current_groups = self._groups(current_shipments, current_invoices, dimension)
        previous_groups = self._groups(previous_shipments, previous_invoices, dimension)
        rows = []
        for dimension_id, group in current_groups.items():
            prior = previous_groups.get(dimension_id, {"shipments": [], "invoices": [], "label": group["label"]})
            values: dict[str, Decimal | None] = {}
            comparisons: dict[str, dict | None] = {}
            coverage: dict[str, dict] = {}
            for key in metric_keys:
                current = self.calculator.calculate(
                    key, group["shipments"], group["invoices"], period, selected_currency
                )
                previous = self.calculator.calculate(
                    key,
                    prior["shipments"],
                    prior["invoices"],
                    comparison_period,
                    selected_currency,
                )
                values[key] = current.value
                comparisons[key] = compare_values(
                    current.value, previous.value, metric_definition(key).unit
                )
                coverage[key] = current.coverage
            rows.append(
                {
                    "dimension_id": dimension_id,
                    "dimension_label": group["label"],
                    "values": values,
                    "comparisons": comparisons,
                    "coverage": coverage,
                    "drilldown": {
                        "dimension": dimension,
                        "dimension_id": dimension_id,
                    },
                }
            )
        sort_key = sort_by or metric_keys[0]
        if sort_key not in metric_keys and sort_key != "label":
            raise ValueError("sort_by must be label or one of the requested metrics.")
        reverse = sort_order.lower() != "asc"
        if sort_key == "label":
            rows.sort(key=lambda item: item["dimension_label"].lower(), reverse=reverse)
        else:
            rows.sort(
                key=lambda item: (
                    item["values"].get(sort_key) is not None,
                    item["values"].get(sort_key) or Decimal("0"),
                ),
                reverse=reverse,
            )
        total = len(rows)
        offset = (page - 1) * page_size
        return {
            "period": period.response(),
            "comparison_period": comparison_period.response(),
            "dimension": dimension,
            "currency": selected_currency,
            "filters": filters.response(),
            "metrics": [metric_definition(key).response() for key in metric_keys],
            "rows": rows[offset : offset + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        }

    def insights(
        self,
        from_date: date | None,
        to_date: date | None,
        currency: str | None,
        filters: AnalyticsFilters,
        baseline_window: str,
        limit: int,
    ) -> dict:
        period = self.resolve_period(from_date, to_date)
        selected_currency = self._currency(currency)
        return InsightEngine(
            repository=self.repository,
            calculator=self.calculator,
            settings=self._settings(),
        ).detect(
            period=period,
            currency=selected_currency,
            filters=filters,
            baseline_window=baseline_window,
            limit=limit,
        )

    def drilldown(
        self,
        metric_key: str,
        from_date: date | None,
        to_date: date | None,
        currency: str | None,
        filters: AnalyticsFilters,
        dimension: str | None,
        dimension_id: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        self._validate_metrics([metric_key])
        if bool(dimension) != bool(dimension_id):
            raise ValueError("dimension and dimension_id must be supplied together.")
        if dimension and dimension not in ALL_DIMENSIONS:
            raise ValueError(f"Unsupported dimension: {dimension}")
        period = self.resolve_period(from_date, to_date)
        selected_currency = self._currency(currency)
        shipments = self.repository.shipment_facts(period.from_date, period.to_date, filters)
        invoices = self.repository.invoice_facts(period.to_date, filters)
        if dimension and dimension_id:
            shipments = [item for item in shipments if item.dimension(dimension)[0] == dimension_id]
            invoices = [item for item in invoices if item.dimension(dimension)[0] == dimension_id]
        result = self.calculator.calculate(
            metric_key, shipments, invoices, period, selected_currency
        )
        if metric_key in INVOICE_METRICS:
            items = self._invoice_drilldown(metric_key, invoices, period, selected_currency)
        else:
            items = self._shipment_drilldown(metric_key, shipments, selected_currency)
        items.sort(key=lambda item: item["record_date"], reverse=True)
        total = len(items)
        offset = (page - 1) * page_size
        return {
            "metric": metric_definition(metric_key).response(),
            "period": period.response(),
            "currency": selected_currency,
            "filters": filters.response(),
            "dimension": dimension,
            "dimension_id": dimension_id,
            "reconciled_value": result.value,
            "coverage": result.coverage,
            "items": items[offset : offset + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, math.ceil(total / page_size)),
        }

    def resolve_period(self, from_date: date | None, to_date: date | None) -> Period:
        latest = self.repository.latest_date() or date.today()
        resolved_to = to_date or latest
        resolved_from = from_date or (resolved_to - timedelta(days=89))
        if resolved_from > resolved_to:
            raise ValueError("from_date must be on or before to_date.")
        return Period(resolved_from, resolved_to)

    def _groups(
        self,
        shipments: list[ShipmentFact],
        invoices: list[InvoiceFact],
        dimension: str,
    ) -> dict[str, dict]:
        groups: dict[str, dict] = {}
        for shipment in shipments:
            identifier, label = shipment.dimension(dimension)
            group = groups.setdefault(identifier, {"label": label, "shipments": [], "invoices": []})
            group["shipments"].append(shipment)
        for invoice in invoices:
            identifier, label = invoice.dimension(dimension)
            group = groups.setdefault(identifier, {"label": label, "shipments": [], "invoices": []})
            group["invoices"].append(invoice)
        return groups

    @staticmethod
    def _shipment_drilldown(
        metric_key: str, shipments: list[ShipmentFact], currency: str
    ) -> list[dict]:
        items = []
        for shipment in shipments:
            revenue = shipment.revenue if shipment.currency == currency else None
            cost = shipment.cost(currency)
            include = True
            if metric_key in {"revenue", "revenue_per_shipment", "revenue_per_teu"}:
                include = revenue is not None
            elif metric_key in {"cost", "cost_per_shipment", "cost_per_teu"}:
                include = cost is not None
            elif metric_key in {"teu", "route_concentration"}:
                include = shipment.teu > 0
            elif metric_key == "gross_weight":
                include = shipment.gross_weight is not None
            elif metric_key in {"loaded_containers", "empty_containers", "loaded_empty_ratio"}:
                include = any(
                    (item.status or "").lower() in {"loaded", "empty"}
                    for item in shipment.containers
                )
            if not include:
                continue
            source_document_ids = {
                item.source_document_id
                for item in shipment.containers
                if item.source_document_id is not None
            }
            source_document_ids.update(shipment.source_document_ids)
            items.append(
                {
                    "record_type": "shipment",
                    "record_id": shipment.id,
                    "label": shipment.reference or str(shipment.id),
                    "record_date": shipment.operational_date,
                    "customer": shipment.customer_name,
                    "route": shipment.route_label,
                    "revenue": revenue,
                    "cost": cost,
                    "teu": shipment.teu,
                    "gross_weight": shipment.gross_weight,
                    "invoice_total": None,
                    "outstanding": None,
                    "currency": currency if revenue is not None or cost is not None else shipment.currency,
                    "shipment_id": shipment.id,
                    "invoice_id": None,
                    "cost_record_ids": [item.id for item in shipment.costs if item.currency == currency],
                    "container_ids": [item.id for item in shipment.containers],
                    "source_document_ids": sorted(source_document_ids, key=str),
                    "import_job_id": shipment.import_job_id,
                    "source_row_number": shipment.source_row_number,
                }
            )
        return items

    @staticmethod
    def _invoice_drilldown(
        metric_key: str,
        invoices: list[InvoiceFact],
        period: Period,
        currency: str,
    ) -> list[dict]:
        items = []
        for invoice in invoices:
            if invoice.currency != currency:
                continue
            outstanding = invoice.balance(period.to_date, currency)
            if metric_key in {"invoice_value", "average_invoice_value", "average_payment_delay"}:
                if not (period.from_date <= invoice.invoice_date <= period.to_date and invoice.direction == "receivable"):
                    continue
            elif metric_key == "outstanding_receivables":
                if invoice.direction != "receivable" or not outstanding:
                    continue
            elif metric_key == "outstanding_payables":
                if invoice.direction != "payable" or not outstanding:
                    continue
            items.append(
                {
                    "record_type": "invoice",
                    "record_id": invoice.id,
                    "label": invoice.invoice_number,
                    "record_date": invoice.invoice_date,
                    "customer": invoice.customer_name or invoice.supplier_name,
                    "route": invoice.route_label,
                    "revenue": None,
                    "cost": None,
                    "teu": None,
                    "gross_weight": None,
                    "invoice_total": invoice.total,
                    "outstanding": outstanding,
                    "currency": invoice.currency,
                    "shipment_id": invoice.shipment_id,
                    "invoice_id": invoice.id,
                    "cost_record_ids": [],
                    "container_ids": [],
                    "source_document_ids": [invoice.source_document_id] if invoice.source_document_id else [],
                    "import_job_id": None,
                    "source_row_number": None,
                }
            )
        return items

    @staticmethod
    def _bucket_label(value: date, grain: str) -> str:
        if grain == "day":
            return value.isoformat()
        if grain == "week":
            iso = value.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        if grain == "month":
            return value.strftime("%Y-%m")
        if grain == "quarter":
            return f"{value.year}-Q{((value.month - 1) // 3) + 1}"
        return str(value.year)

    @staticmethod
    def _validate_metrics(keys: list[str]) -> None:
        if not keys:
            raise ValueError("At least one metric is required.")
        if len(keys) > 12:
            raise ValueError("At most 12 metrics may be requested.")
        for key in keys:
            metric_definition(key)

    def _currency(self, value: str | None) -> str:
        resolved = (value or self.company.default_currency).strip().upper()
        if len(resolved) != 3 or not resolved.isalpha():
            raise ValueError("currency must be a three-letter code.")
        return resolved

    @staticmethod
    def _settings():
        from app.config import get_settings

        return get_settings()
