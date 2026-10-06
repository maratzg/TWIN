from collections import defaultdict
from datetime import date
from decimal import Decimal
import uuid

from app.analytics.comparisons import compare_values
from app.analytics.metrics import MetricCalculator, safe_divide
from app.analytics.query import AnalyticsFilters, AnalyticsQueryRepository, InvoiceFact, ShipmentFact
from app.analytics.time import Period, baseline_period


INSIGHT_NAMESPACE = uuid.UUID("cb03139f-3800-4af4-9845-c3011eb12ef8")
ZERO = Decimal("0")


def _decimal(value: float | str | Decimal) -> Decimal:
    return Decimal(str(value))


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    if count % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


class InsightEngine:
    def __init__(self, repository: AnalyticsQueryRepository, calculator: MetricCalculator, settings) -> None:
        self.repository = repository
        self.calculator = calculator
        self.settings = settings

    def detect(
        self,
        *,
        period: Period,
        currency: str,
        filters: AnalyticsFilters,
        baseline_window: str,
        limit: int,
    ) -> dict:
        baseline = baseline_period(period, baseline_window)
        current_shipments = self.repository.shipment_facts(period.from_date, period.to_date, filters)
        current_invoices = self.repository.invoice_facts(period.to_date, filters)
        baseline_shipments = self.repository.shipment_facts(baseline.from_date, baseline.to_date, filters)
        baseline_invoices = self.repository.invoice_facts(baseline.to_date, filters)
        insights: list[dict] = []

        current_routes = self._shipment_groups(current_shipments, "route")
        baseline_routes = self._shipment_groups(baseline_shipments, "route")
        min_route = self.settings.analytics_min_route_shipments
        margin_drop = _decimal(self.settings.analytics_margin_drop_pp)
        cost_increase = _decimal(self.settings.analytics_cost_increase_pct)
        volume_change = _decimal(self.settings.analytics_volume_change_pct)

        for entity_id, group in current_routes.items():
            prior = baseline_routes.get(entity_id)
            if not prior or len(group["facts"]) < min_route or len(prior["facts"]) < min_route:
                continue
            current_margin = self._metric("contribution_margin", group["facts"], [], period, currency)
            baseline_margin = self._metric("contribution_margin", prior["facts"], [], baseline, currency)
            if current_margin is None or baseline_margin is None:
                continue
            margin_delta = current_margin - baseline_margin
            current_cost_teu = self._metric("cost_per_teu", group["facts"], [], period, currency)
            baseline_cost_teu = self._metric("cost_per_teu", prior["facts"], [], baseline, currency)
            current_revenue_teu = self._metric("revenue_per_teu", group["facts"], [], period, currency)
            baseline_revenue_teu = self._metric("revenue_per_teu", prior["facts"], [], baseline, currency)
            current_teu = self._metric("teu", group["facts"], [], period, currency)
            baseline_teu = self._metric("teu", prior["facts"], [], baseline, currency)
            cost_change = self._percent_change(current_cost_teu, baseline_cost_teu)
            if margin_delta <= -margin_drop:
                contributors = [
                    self._contributor("cost_per_teu", current_cost_teu, baseline_cost_teu, "currency_per_teu"),
                    self._contributor("revenue_per_teu", current_revenue_teu, baseline_revenue_teu, "currency_per_teu"),
                    self._contributor("teu", current_teu, baseline_teu, "teu"),
                ]
                current_revenue = self._metric("revenue", group["facts"], [], period, currency) or ZERO
                insights.append(
                    self._insight(
                        type_="margin_deterioration",
                        severity="critical" if margin_delta <= -(margin_drop * 2) else "warning",
                        title="Route contribution margin deteriorated",
                        entity_type="route",
                        entity_id=entity_id,
                        entity_label=group["label"],
                        metric="contribution_margin",
                        current=current_margin,
                        baseline_value=baseline_margin,
                        unit="percent",
                        contributors=contributors,
                        period=period,
                        baseline=baseline,
                        evidence={
                            "current_shipments": len(group["facts"]),
                            "baseline_shipments": len(prior["facts"]),
                            "current_revenue": current_revenue,
                            "cost_per_teu_change_pct": cost_change,
                            "interpretation": "contributors_not_causes",
                        },
                        rank=abs(margin_delta) * (Decimal("1") + current_revenue / Decimal("100000")),
                    )
                )
            elif cost_change is not None and cost_change >= cost_increase:
                insights.append(
                    self._insight(
                        type_="cost_increase",
                        severity="warning",
                        title="Route cost per TEU increased",
                        entity_type="route",
                        entity_id=entity_id,
                        entity_label=group["label"],
                        metric="cost_per_teu",
                        current=current_cost_teu,
                        baseline_value=baseline_cost_teu,
                        unit="currency_per_teu",
                        contributors=[self._contributor("contribution_margin", current_margin, baseline_margin, "percent")],
                        period=period,
                        baseline=baseline,
                        evidence={"current_shipments": len(group["facts"]), "baseline_shipments": len(prior["facts"])},
                        rank=cost_change,
                    )
                )
            current_daily_teu = safe_divide(current_teu or ZERO, period.days)
            baseline_daily_teu = safe_divide(baseline_teu or ZERO, baseline.days)
            daily_change = self._percent_change(current_daily_teu, baseline_daily_teu)
            if daily_change is not None and abs(daily_change) >= volume_change:
                insights.append(
                    self._insight(
                        type_="volume_anomaly",
                        severity="info",
                        title="Route TEU volume changed materially",
                        entity_type="route",
                        entity_id=entity_id,
                        entity_label=group["label"],
                        metric="teu",
                        current=current_teu,
                        baseline_value=baseline_teu,
                        unit="teu",
                        contributors=[],
                        period=period,
                        baseline=baseline,
                        evidence={
                            "current_daily_teu": current_daily_teu,
                            "baseline_daily_teu": baseline_daily_teu,
                            "daily_rate_change_pct": daily_change,
                            "current_shipments": len(group["facts"]),
                            "baseline_shipments": len(prior["facts"]),
                        },
                        rank=abs(daily_change) / Decimal("2"),
                    )
                )

        current_revenue = self._metric("revenue", current_shipments, current_invoices, period, currency)
        baseline_revenue = self._metric("revenue", baseline_shipments, baseline_invoices, baseline, currency)
        current_margin = self._metric("contribution_margin", current_shipments, current_invoices, period, currency)
        baseline_margin = self._metric("contribution_margin", baseline_shipments, baseline_invoices, baseline, currency)
        revenue_change = self._percent_change(
            safe_divide(current_revenue or ZERO, period.days),
            safe_divide(baseline_revenue or ZERO, baseline.days),
        )
        margin_change = (
            current_margin - baseline_margin
            if current_margin is not None and baseline_margin is not None
            else None
        )
        revenue_threshold = _decimal(self.settings.analytics_revenue_change_pct)
        if (
            revenue_change is not None
            and revenue_change >= revenue_threshold
            and margin_change is not None
            and margin_change <= -_decimal(self.settings.analytics_company_margin_decline_pp)
        ):
            insights.append(
                self._insight(
                    type_="revenue_growth_margin_decline",
                    severity="critical",
                    title="Revenue grew while contribution margin declined",
                    entity_type="company",
                    entity_id=None,
                    entity_label="Company",
                    metric="revenue",
                    current=current_revenue,
                    baseline_value=baseline_revenue,
                    unit="currency",
                    contributors=[self._contributor("contribution_margin", current_margin, baseline_margin, "percent")],
                    period=period,
                    baseline=baseline,
                    evidence={"daily_revenue_change_pct": revenue_change},
                    rank=Decimal("150") + abs(margin_change),
                )
            )
        elif revenue_change is not None and abs(revenue_change) >= revenue_threshold:
            insights.append(
                self._insight(
                    type_="revenue_change",
                    severity="info",
                    title="Revenue changed materially",
                    entity_type="company",
                    entity_id=None,
                    entity_label="Company",
                    metric="revenue",
                    current=current_revenue,
                    baseline_value=baseline_revenue,
                    unit="currency",
                    contributors=[],
                    period=period,
                    baseline=baseline,
                    evidence={"daily_revenue_change_pct": revenue_change},
                    rank=abs(revenue_change),
                )
            )

        insights.extend(
            self._concentration_insights(
                current_shipments, current_invoices, period, baseline, currency
            )
        )
        insights.extend(
            self._payment_insights(
                current_invoices, baseline_invoices, period, baseline, currency
            )
        )
        insights.extend(
            self._customer_improvements(
                current_shipments, baseline_shipments, period, baseline, currency
            )
        )
        insights.extend(self._expensive_shipments(current_shipments, period, baseline, currency))

        deduplicated: dict[tuple[str, str | None, str], dict] = {}
        for insight in insights:
            key = (insight["type"], insight["entity_id"], insight["metric"])
            existing = deduplicated.get(key)
            if existing is None or insight["rank_score"] > existing["rank_score"]:
                deduplicated[key] = insight
        ranked = sorted(
            deduplicated.values(),
            key=lambda item: (self._severity_weight(item["severity"]), item["rank_score"]),
            reverse=True,
        )[:limit]
        return {
            "period": period.response(),
            "baseline_period": baseline.response(),
            "baseline_window": baseline_window,
            "currency": currency,
            "filters": filters.response(),
            "insights": ranked,
        }

    def _concentration_insights(
        self,
        shipments: list[ShipmentFact],
        invoices: list[InvoiceFact],
        period: Period,
        baseline: Period,
        currency: str,
    ) -> list[dict]:
        insights: list[dict] = []
        customer_groups = self._shipment_groups(shipments, "customer")
        revenue_groups: list[tuple[str, str, Decimal, int]] = []
        total_revenue = ZERO
        for identifier, group in customer_groups.items():
            value = self._metric("revenue", group["facts"], [], period, currency) or ZERO
            total_revenue += value
            if identifier != "unassigned":
                revenue_groups.append((identifier, group["label"], value, len(group["facts"])))
        minimum_shipments = self.settings.analytics_min_route_shipments
        if revenue_groups and total_revenue > 0 and len(shipments) >= minimum_shipments:
            identifier, label, value, sample = max(revenue_groups, key=lambda item: item[2])
            share = value / total_revenue * Decimal("100")
            threshold = _decimal(self.settings.analytics_customer_concentration_pct)
            if share >= threshold:
                insights.append(
                    self._insight(
                        type_="customer_concentration",
                        severity="warning",
                        title="Revenue is concentrated in one customer",
                        entity_type="customer",
                        entity_id=identifier,
                        entity_label=label,
                        metric="customer_concentration",
                        current=share,
                        baseline_value=None,
                        unit="percent",
                        contributors=[],
                        period=period,
                        baseline=baseline,
                        evidence={"customer_revenue": value, "total_revenue": total_revenue, "shipments": sample},
                        rank=share,
                    )
                )
        route_groups = self._shipment_groups(shipments, "route")
        total_teu = sum((item.teu for item in shipments), ZERO)
        route_values = [
            (identifier, group["label"], sum((item.teu for item in group["facts"]), ZERO), len(group["facts"]))
            for identifier, group in route_groups.items()
            if identifier != "unresolved"
        ]
        if route_values and total_teu > 0 and len(shipments) >= minimum_shipments:
            identifier, label, value, sample = max(route_values, key=lambda item: item[2])
            share = value / total_teu * Decimal("100")
            if share >= _decimal(self.settings.analytics_route_concentration_pct):
                insights.append(
                    self._insight(
                        type_="route_concentration",
                        severity="warning",
                        title="TEU volume is concentrated on one route",
                        entity_type="route",
                        entity_id=identifier,
                        entity_label=label,
                        metric="route_concentration",
                        current=share,
                        baseline_value=None,
                        unit="percent",
                        contributors=[],
                        period=period,
                        baseline=baseline,
                        evidence={"route_teu": value, "total_teu": total_teu, "shipments": sample},
                        rank=share - Decimal("5"),
                    )
                )
        receivables: dict[str, dict] = {}
        total_outstanding = ZERO
        for invoice in invoices:
            if invoice.direction != "receivable" or invoice.currency != currency:
                continue
            balance = invoice.balance(period.to_date, currency) or ZERO
            if balance <= 0:
                continue
            identifier = str(invoice.customer_id) if invoice.customer_id else "unassigned"
            item = receivables.setdefault(identifier, {"label": invoice.customer_name or "Unassigned customer", "balance": ZERO, "overdue": ZERO, "count": 0})
            item["balance"] += balance
            item["count"] += 1
            if invoice.due_date and invoice.due_date < period.to_date:
                item["overdue"] += balance
            total_outstanding += balance
        outstanding_invoice_count = sum(value["count"] for value in receivables.values())
        if (
            receivables
            and total_outstanding > 0
            and outstanding_invoice_count >= self.settings.analytics_min_receivable_invoices
        ):
            identifier, value = max(receivables.items(), key=lambda item: item[1]["balance"])
            share = value["balance"] / total_outstanding * Decimal("100")
            if share >= _decimal(self.settings.analytics_receivable_concentration_pct) and value["overdue"] > 0:
                insights.append(
                    self._insight(
                        type_="outstanding_receivable_risk",
                        severity="warning",
                        title="Outstanding receivables are concentrated",
                        entity_type="customer",
                        entity_id=None if identifier == "unassigned" else identifier,
                        entity_label=value["label"],
                        metric="outstanding_receivables",
                        current=value["balance"],
                        baseline_value=None,
                        unit="currency",
                        contributors=[],
                        period=period,
                        baseline=baseline,
                        evidence={"share_pct": share, "overdue_balance": value["overdue"], "invoice_count": value["count"]},
                        rank=share + value["overdue"] / Decimal("10000"),
                    )
                )
        return insights

    def _payment_insights(
        self,
        current: list[InvoiceFact],
        prior: list[InvoiceFact],
        period: Period,
        baseline: Period,
        currency: str,
    ) -> list[dict]:
        insights: list[dict] = []
        current_groups = self._invoice_groups(current, "customer")
        prior_groups = self._invoice_groups(prior, "customer")
        threshold = _decimal(self.settings.analytics_payment_delay_days)
        minimum = self.settings.analytics_min_paid_invoices
        for identifier, group in current_groups.items():
            if identifier == "unassigned" or identifier not in prior_groups:
                continue
            current_result = self.calculator.calculate(
                "average_payment_delay", [], group["facts"], period, currency
            )
            prior_result = self.calculator.calculate(
                "average_payment_delay", [], prior_groups[identifier]["facts"], baseline, currency
            )
            if (
                current_result.value is None
                or prior_result.value is None
                or int(current_result.components.get("paid_invoices", 0)) < minimum
                or int(prior_result.components.get("paid_invoices", 0)) < minimum
            ):
                continue
            change = current_result.value - prior_result.value
            if change >= threshold:
                insights.append(
                    self._insight(
                        type_="payment_deterioration",
                        severity="warning",
                        title="Customer payment delay deteriorated",
                        entity_type="customer",
                        entity_id=identifier,
                        entity_label=group["label"],
                        metric="average_payment_delay",
                        current=current_result.value,
                        baseline_value=prior_result.value,
                        unit="days",
                        contributors=[],
                        period=period,
                        baseline=baseline,
                        evidence={
                            "current_paid_invoices": current_result.components["paid_invoices"],
                            "baseline_paid_invoices": prior_result.components["paid_invoices"],
                        },
                        rank=change * Decimal("4"),
                    )
                )
        return insights

    def _customer_improvements(
        self,
        current: list[ShipmentFact],
        prior: list[ShipmentFact],
        period: Period,
        baseline: Period,
        currency: str,
    ) -> list[dict]:
        insights: list[dict] = []
        current_groups = self._shipment_groups(current, "customer")
        prior_groups = self._shipment_groups(prior, "customer")
        threshold = _decimal(self.settings.analytics_margin_improvement_pp)
        minimum = self.settings.analytics_min_route_shipments
        for identifier, group in current_groups.items():
            previous = prior_groups.get(identifier)
            if identifier == "unassigned" or not previous or len(group["facts"]) < minimum or len(previous["facts"]) < minimum:
                continue
            current_margin = self._metric("contribution_margin", group["facts"], [], period, currency)
            previous_margin = self._metric("contribution_margin", previous["facts"], [], baseline, currency)
            if current_margin is None or previous_margin is None:
                continue
            change = current_margin - previous_margin
            if change >= threshold:
                insights.append(
                    self._insight(
                        type_="customer_profitability_improvement",
                        severity="positive",
                        title="Customer contribution margin improved",
                        entity_type="customer",
                        entity_id=identifier,
                        entity_label=group["label"],
                        metric="contribution_margin",
                        current=current_margin,
                        baseline_value=previous_margin,
                        unit="percent",
                        contributors=[],
                        period=period,
                        baseline=baseline,
                        evidence={"current_shipments": len(group["facts"]), "baseline_shipments": len(previous["facts"])},
                        rank=change,
                    )
                )
        return insights

    def _expensive_shipments(
        self,
        shipments: list[ShipmentFact],
        period: Period,
        baseline: Period,
        currency: str,
    ) -> list[dict]:
        insights: list[dict] = []
        groups = self._shipment_groups(shipments, "route")
        minimum = self.settings.analytics_min_anomaly_observations
        threshold = _decimal(self.settings.analytics_expensive_shipment_zscore)
        for _, group in groups.items():
            values = [
                (item, (item.cost(currency) or ZERO) / item.teu)
                for item in group["facts"]
                if item.cost(currency) is not None and item.teu > 0
            ]
            if len(values) < minimum:
                continue
            median = _median([value for _, value in values])
            mad = _median([abs(value - median) for _, value in values])
            if mad == 0:
                continue
            for shipment, value in values:
                robust_z = Decimal("0.6745") * (value - median) / mad
                if robust_z < threshold:
                    continue
                insights.append(
                    self._insight(
                        type_="expensive_shipment_anomaly",
                        severity="critical" if robust_z >= threshold * Decimal("1.5") else "warning",
                        title="Shipment cost per TEU is unusually high",
                        entity_type="shipment",
                        entity_id=str(shipment.id),
                        entity_label=shipment.reference or str(shipment.id),
                        metric="cost_per_teu",
                        current=value,
                        baseline_value=median,
                        unit="currency_per_teu",
                        contributors=[],
                        period=period,
                        baseline=baseline,
                        evidence={"route": group["label"], "route_observations": len(values), "median": median, "mad": mad, "robust_zscore": robust_z},
                        rank=robust_z * Decimal("12"),
                    )
                )
        return insights

    def _metric(
        self,
        key: str,
        shipments: list[ShipmentFact],
        invoices: list[InvoiceFact],
        period: Period,
        currency: str,
    ) -> Decimal | None:
        return self.calculator.calculate(key, shipments, invoices, period, currency).value

    @staticmethod
    def _shipment_groups(facts: list[ShipmentFact], dimension: str) -> dict[str, dict]:
        groups: dict[str, dict] = {}
        for fact in facts:
            identifier, label = fact.dimension(dimension)
            group = groups.setdefault(identifier, {"label": label, "facts": []})
            group["facts"].append(fact)
        return groups

    @staticmethod
    def _invoice_groups(facts: list[InvoiceFact], dimension: str) -> dict[str, dict]:
        groups: dict[str, dict] = {}
        for fact in facts:
            identifier, label = fact.dimension(dimension)
            group = groups.setdefault(identifier, {"label": label, "facts": []})
            group["facts"].append(fact)
        return groups

    @staticmethod
    def _percent_change(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
        if current is None or previous in {None, ZERO}:
            return None
        return (current - previous) / previous * Decimal("100")

    @staticmethod
    def _contributor(
        metric: str,
        current: Decimal | None,
        baseline: Decimal | None,
        unit: str,
    ) -> dict:
        comparison = compare_values(current, baseline, unit)
        return {
            "metric": metric,
            "current_value": current,
            "baseline_value": baseline,
            "absolute_change": comparison["absolute_change"],
            "percentage_change": comparison["percentage_change"],
            "change_type": comparison["change_type"],
        }

    @staticmethod
    def _insight(
        *,
        type_: str,
        severity: str,
        title: str,
        entity_type: str,
        entity_id: str | None,
        entity_label: str,
        metric: str,
        current: Decimal | None,
        baseline_value: Decimal | None,
        unit: str,
        contributors: list[dict],
        period: Period,
        baseline: Period,
        evidence: dict,
        rank: Decimal,
    ) -> dict:
        comparison = compare_values(current, baseline_value, unit)
        identifier = str(
            uuid.uuid5(
                INSIGHT_NAMESPACE,
                f"{type_}:{entity_id}:{metric}:{period.from_date}:{period.to_date}",
            )
        )
        drilldown = {"metric": metric}
        if entity_type in {"route", "customer", "vessel", "voyage", "pol", "pod"} and entity_id:
            drilldown.update({"dimension": entity_type, "dimension_id": entity_id})
        if entity_type == "shipment" and entity_id:
            drilldown.update({"record_type": "shipment", "record_id": entity_id})
        return {
            "id": identifier,
            "type": type_,
            "severity": severity,
            "title": title,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_label": entity_label,
            "metric": metric,
            "current_value": current,
            "baseline_value": baseline_value,
            "absolute_change": comparison["absolute_change"],
            "percentage_change": comparison["percentage_change"],
            "change_type": comparison["change_type"],
            "contributors": contributors,
            "period": period.response(),
            "baseline_period": baseline.response(),
            "evidence": evidence,
            "drilldown": drilldown,
            "rank_score": rank,
        }

    @staticmethod
    def _severity_weight(value: str) -> int:
        return {"critical": 4, "warning": 3, "positive": 2, "info": 1}.get(value, 0)
