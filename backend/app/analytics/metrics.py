from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.analytics.query import InvoiceFact, ShipmentFact
from app.analytics.registry import metric_definition
from app.analytics.time import Period


ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class Calculation:
    value: Decimal | None
    coverage: dict
    components: dict[str, Decimal | int | None]


def safe_divide(numerator: Decimal, denominator: Decimal | int) -> Decimal | None:
    denominator_decimal = Decimal(str(denominator))
    if denominator_decimal == ZERO:
        return None
    return numerator / denominator_decimal


def percent(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    result = safe_divide(numerator, denominator)
    return result * HUNDRED if result is not None else None


class MetricCalculator:
    def calculate(
        self,
        key: str,
        shipments: list[ShipmentFact],
        invoices: list[InvoiceFact],
        period: Period,
        currency: str,
    ) -> Calculation:
        metric_definition(key)
        revenue_facts = [item for item in shipments if item.revenue is not None and item.currency == currency]
        cost_facts = [item for item in shipments if item.cost(currency) is not None]
        both_facts = [item for item in shipments if item.revenue is not None and item.currency == currency and item.cost(currency) is not None]
        revenue = sum((item.revenue for item in revenue_facts if item.revenue is not None), ZERO)
        cost = sum((item.cost(currency) or ZERO for item in cost_facts), ZERO)
        contribution_revenue = sum(
            (item.revenue for item in both_facts if item.revenue is not None), ZERO
        )
        contribution_cost = sum((item.cost(currency) or ZERO for item in both_facts), ZERO)
        profit = contribution_revenue - contribution_cost
        containers = [container for item in shipments for container in item.containers]
        valid_teu = [container for container in containers if container.teu is not None]
        teu = sum((container.teu for container in valid_teu if container.teu is not None), ZERO)
        gross_weight_facts = [item for item in shipments if item.gross_weight is not None]
        gross_weight = sum((item.gross_weight for item in gross_weight_facts if item.gross_weight is not None), ZERO)
        loaded = [item for item in containers if (item.status or "").strip().lower() == "loaded"]
        empty = [item for item in containers if (item.status or "").strip().lower() == "empty"]
        explicit_status = loaded + empty
        revenue_teu = sum((item.teu for item in revenue_facts), ZERO)
        cost_teu = sum((item.teu for item in cost_facts), ZERO)
        finance_fact_ids = {item.id for item in both_facts}
        finance_teu = sum((item.teu for item in both_facts), ZERO)
        flow_invoices = [
            item
            for item in invoices
            if period.from_date <= item.invoice_date <= period.to_date and item.currency == currency
        ]
        receivables = [item for item in flow_invoices if item.direction == "receivable"]
        receivable_value = sum((item.total for item in receivables), ZERO)
        all_receivables = [
            item for item in invoices
            if item.direction == "receivable" and item.currency == currency and item.invoice_date <= period.to_date
        ]
        all_payables = [
            item for item in invoices
            if item.direction == "payable" and item.currency == currency and item.invoice_date <= period.to_date
        ]
        outstanding_receivables = sum((item.balance(period.to_date, currency) or ZERO for item in all_receivables), ZERO)
        outstanding_payables = sum((item.balance(period.to_date, currency) or ZERO for item in all_payables), ZERO)
        delay_eligible = [item for item in receivables if item.due_date is not None]
        delays: list[int] = []
        for item in delay_eligible:
            final_date = item.final_payment_date(period.to_date, currency)
            if final_date is not None and item.due_date is not None:
                delays.append((final_date - item.due_date).days)
        revenue_exclusions = self._counts_by_currency(
            [item.currency for item in shipments if item.revenue is not None and item.currency != currency]
        )
        cost_exclusions = self._counts_by_currency(
            [component.currency for item in shipments for component in item.costs if component.currency != currency]
        )
        invoice_exclusions = self._counts_by_currency(
            [item.currency for item in invoices if period.from_date <= item.invoice_date <= period.to_date and item.currency != currency]
        )
        if key == "revenue":
            return Calculation(revenue, self._coverage(len(revenue_facts), len(shipments), "shipments with revenue", revenue_exclusions), {"revenue": revenue})
        if key == "cost":
            return Calculation(cost, self._coverage(len(cost_facts), len(shipments), "shipments with attributable cost", cost_exclusions), {"cost": cost})
        if key == "contribution_profit":
            return Calculation(profit, self._coverage(len(both_facts), len(shipments), "shipments with revenue and cost", self._merge_counts(revenue_exclusions, cost_exclusions)), {"revenue": contribution_revenue, "cost": contribution_cost})
        if key == "contribution_margin":
            return Calculation(percent(profit, contribution_revenue), self._coverage(len(both_facts), len(shipments), "shipments with revenue and cost", self._merge_counts(revenue_exclusions, cost_exclusions)), {"revenue": contribution_revenue, "cost": contribution_cost, "profit": profit})
        if key == "shipments":
            return Calculation(Decimal(len(shipments)), self._coverage(len(shipments), len(shipments), "shipments with operational date"), {"shipments": len(shipments)})
        if key == "containers":
            return Calculation(Decimal(len(containers)), self._coverage(len(containers), len(containers), "canonical container occurrences"), {"containers": len(containers)})
        if key == "loaded_containers":
            return Calculation(Decimal(len(loaded)), self._coverage(len(explicit_status), len(containers), "containers with explicit loaded/empty status"), {"loaded": len(loaded), "empty": len(empty)})
        if key == "empty_containers":
            return Calculation(Decimal(len(empty)), self._coverage(len(explicit_status), len(containers), "containers with explicit loaded/empty status"), {"loaded": len(loaded), "empty": len(empty)})
        if key == "loaded_empty_ratio":
            return Calculation(safe_divide(Decimal(len(loaded)), len(empty)), self._coverage(len(explicit_status), len(containers), "containers with explicit loaded/empty status"), {"loaded": len(loaded), "empty": len(empty)})
        if key == "teu":
            return Calculation(teu, self._coverage(len(valid_teu), len(containers), "containers with valid TEU"), {"teu": teu, "containers": len(containers)})
        if key == "gross_weight":
            return Calculation(gross_weight, self._coverage(len(gross_weight_facts), len(shipments), "shipments with gross weight"), {"gross_weight": gross_weight})
        if key == "revenue_per_shipment":
            return Calculation(safe_divide(revenue, len(revenue_facts)), self._coverage(len(revenue_facts), len(shipments), "revenue-bearing shipments", revenue_exclusions), {"revenue": revenue, "shipments": len(revenue_facts)})
        if key == "cost_per_shipment":
            return Calculation(safe_divide(cost, len(cost_facts)), self._coverage(len(cost_facts), len(shipments), "cost-bearing shipments", cost_exclusions), {"cost": cost, "shipments": len(cost_facts)})
        if key == "profit_per_shipment":
            return Calculation(safe_divide(profit, len(both_facts)), self._coverage(len(both_facts), len(shipments), "shipments with revenue and cost", self._merge_counts(revenue_exclusions, cost_exclusions)), {"profit": profit, "shipments": len(both_facts)})
        if key == "revenue_per_teu":
            return Calculation(safe_divide(revenue, revenue_teu), self._coverage(sum(item.valid_teu_containers for item in revenue_facts), sum(len(item.containers) for item in revenue_facts), "revenue-bearing containers with valid TEU", revenue_exclusions), {"revenue": revenue, "teu": revenue_teu})
        if key == "cost_per_teu":
            return Calculation(safe_divide(cost, cost_teu), self._coverage(sum(item.valid_teu_containers for item in cost_facts), sum(len(item.containers) for item in cost_facts), "cost-bearing containers with valid TEU", cost_exclusions), {"cost": cost, "teu": cost_teu})
        if key == "profit_per_teu":
            return Calculation(safe_divide(profit, finance_teu), self._coverage(sum(item.valid_teu_containers for item in shipments if item.id in finance_fact_ids), sum(len(item.containers) for item in shipments if item.id in finance_fact_ids), "finance-bearing containers with valid TEU", self._merge_counts(revenue_exclusions, cost_exclusions)), {"profit": profit, "teu": finance_teu})
        if key == "invoice_value":
            return Calculation(receivable_value, self._coverage(len(receivables), len([item for item in flow_invoices if item.direction == "receivable"]), "receivable invoices in selected currency", invoice_exclusions), {"invoice_value": receivable_value, "invoices": len(receivables)})
        if key == "average_invoice_value":
            return Calculation(safe_divide(receivable_value, len(receivables)), self._coverage(len(receivables), len([item for item in flow_invoices if item.direction == "receivable"]), "receivable invoices in selected currency", invoice_exclusions), {"invoice_value": receivable_value, "invoices": len(receivables)})
        if key == "outstanding_receivables":
            return Calculation(outstanding_receivables, self._coverage(len(all_receivables), len(all_receivables), "receivable invoices valued as of period end", invoice_exclusions), {"outstanding": outstanding_receivables, "invoices": len(all_receivables)})
        if key == "outstanding_payables":
            return Calculation(outstanding_payables, self._coverage(len(all_payables), len(all_payables), "payable invoices valued as of period end", invoice_exclusions), {"outstanding": outstanding_payables, "invoices": len(all_payables)})
        if key == "average_payment_delay":
            average = safe_divide(Decimal(sum(delays)), len(delays))
            return Calculation(average, self._coverage(len(delays), len(delay_eligible), "due-dated receivables fully paid by period end"), {"delay_days": sum(delays), "paid_invoices": len(delays)})
        if key == "customer_concentration":
            grouped: dict[str, Decimal] = defaultdict(lambda: ZERO)
            for item in revenue_facts:
                if item.customer_id and item.revenue is not None:
                    grouped[str(item.customer_id)] += item.revenue
            largest = max(grouped.values(), default=ZERO)
            named = sum(1 for item in revenue_facts if item.customer_id)
            return Calculation(percent(largest, revenue), self._coverage(named, len(revenue_facts), "revenue-bearing shipments assigned to customers", revenue_exclusions), {"largest_customer_revenue": largest, "revenue": revenue})
        if key == "route_concentration":
            grouped_teu: dict[str, Decimal] = defaultdict(lambda: ZERO)
            resolved_teu = ZERO
            for item in shipments:
                if item.route_key != "unresolved":
                    grouped_teu[item.route_key] += item.teu
                    resolved_teu += item.teu
            largest = max(grouped_teu.values(), default=ZERO)
            resolved = sum(item.valid_teu_containers for item in shipments if item.route_key != "unresolved")
            return Calculation(percent(largest, teu), self._coverage(resolved, len(valid_teu), "valid TEU on resolved canonical routes"), {"largest_route_teu": largest, "teu": teu, "resolved_teu": resolved_teu})
        raise ValueError(f"Metric calculation is not implemented: {key}")

    @staticmethod
    def _coverage(
        covered: int,
        eligible: int,
        label: str,
        currency_exclusions: dict[str, int] | None = None,
    ) -> dict:
        coverage_percent = (Decimal(covered) / Decimal(eligible) * HUNDRED) if eligible else None
        exclusions = currency_exclusions or {}
        warnings: list[str] = []
        if eligible and covered < eligible:
            warnings.append(f"{eligible - covered} eligible records are missing required data.")
        if exclusions:
            warnings.append("Other currencies were excluded; no FX conversion was applied.")
        return {
            "label": label,
            "covered_records": covered,
            "eligible_records": eligible,
            "percent": coverage_percent,
            "excluded_records": max(eligible - covered, 0) + sum(exclusions.values()),
            "currency_exclusions": exclusions,
            "warnings": warnings,
        }

    @staticmethod
    def _counts_by_currency(values: list[str | None]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for value in values:
            counts[value or "UNKNOWN"] += 1
        return dict(sorted(counts.items()))

    @staticmethod
    def _merge_counts(*values: dict[str, int]) -> dict[str, int]:
        merged: dict[str, int] = defaultdict(int)
        for value in values:
            for key, count in value.items():
                merged[key] += count
        return dict(sorted(merged.items()))
