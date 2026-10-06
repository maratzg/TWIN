from datetime import date
from decimal import Decimal
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field


class AnalyticsPeriod(BaseModel):
    from_date: date
    to_date: date


class MetricMetadata(BaseModel):
    key: str
    display_name: str
    description: str
    unit: str
    calculation: str
    supported_dimensions: list[str]
    date_basis: str
    aggregation: str
    decimals: int


class MetricRegistryResponse(BaseModel):
    metrics: list[MetricMetadata]
    time_grains: list[str]
    dimensions: list[str]


class Coverage(BaseModel):
    label: str
    covered_records: int
    eligible_records: int
    percent: Decimal | None
    excluded_records: int
    currency_exclusions: dict[str, int]
    warnings: list[str]


class Comparison(BaseModel):
    current: Decimal | None
    previous: Decimal | None
    absolute_change: Decimal | None
    percentage_change: Decimal | None
    change_type: Literal["absolute", "percentage_points"]


class MetricValue(BaseModel):
    metric: MetricMetadata
    value: Decimal | None
    currency: str | None
    coverage: Coverage
    comparison: Comparison | None = None
    components: dict[str, Any] = Field(default_factory=dict)


class AnalyticsSummaryResponse(BaseModel):
    period: AnalyticsPeriod
    comparison_period: AnalyticsPeriod
    currency: str
    filters: dict[str, str | None]
    metrics: list[MetricValue]


class DimensionOption(BaseModel):
    id: str
    label: str


class AnalyticsOptionsResponse(BaseModel):
    default_period: AnalyticsPeriod
    default_currency: str
    customers: list[DimensionOption]
    routes: list[DimensionOption]
    ports: list[DimensionOption]
    vessels: list[DimensionOption]
    voyages: list[DimensionOption]
    currencies: list[DimensionOption]


class TimeseriesPoint(BaseModel):
    period: AnalyticsPeriod
    label: str
    values: dict[str, Decimal | None]
    coverage: dict[str, Coverage]


class TimeseriesResponse(BaseModel):
    period: AnalyticsPeriod
    grain: str
    currency: str
    filters: dict[str, str | None]
    metrics: list[MetricMetadata]
    points: list[TimeseriesPoint]


class BreakdownRow(BaseModel):
    dimension_id: str
    dimension_label: str
    values: dict[str, Decimal | None]
    comparisons: dict[str, Comparison | None]
    coverage: dict[str, Coverage]
    drilldown: dict[str, str]


class BreakdownResponse(BaseModel):
    period: AnalyticsPeriod
    comparison_period: AnalyticsPeriod
    dimension: str
    currency: str
    filters: dict[str, str | None]
    metrics: list[MetricMetadata]
    rows: list[BreakdownRow]
    total: int
    page: int
    page_size: int
    pages: int


class InsightContributor(BaseModel):
    metric: str
    current_value: Decimal | None
    baseline_value: Decimal | None
    absolute_change: Decimal | None
    percentage_change: Decimal | None
    change_type: str


class AnalyticsInsight(BaseModel):
    id: str
    type: str
    severity: Literal["info", "warning", "critical", "positive"]
    title: str
    entity_type: str
    entity_id: str | None
    entity_label: str
    metric: str
    current_value: Decimal | None
    baseline_value: Decimal | None
    absolute_change: Decimal | None
    percentage_change: Decimal | None
    change_type: str
    contributors: list[InsightContributor]
    period: AnalyticsPeriod
    baseline_period: AnalyticsPeriod
    evidence: dict[str, Any]
    drilldown: dict[str, str]
    rank_score: Decimal


class InsightsResponse(BaseModel):
    period: AnalyticsPeriod
    baseline_period: AnalyticsPeriod
    baseline_window: str
    currency: str
    filters: dict[str, str | None]
    insights: list[AnalyticsInsight]


class DrilldownItem(BaseModel):
    record_type: Literal["shipment", "invoice"]
    record_id: uuid.UUID
    label: str
    record_date: date
    customer: str | None
    route: str | None
    revenue: Decimal | None
    cost: Decimal | None
    teu: Decimal | None
    gross_weight: Decimal | None
    invoice_total: Decimal | None
    outstanding: Decimal | None
    currency: str | None
    shipment_id: uuid.UUID | None
    invoice_id: uuid.UUID | None
    cost_record_ids: list[uuid.UUID]
    container_ids: list[uuid.UUID]
    source_document_ids: list[uuid.UUID]
    import_job_id: uuid.UUID | None
    source_row_number: int | None


class DrilldownResponse(BaseModel):
    metric: MetricMetadata
    period: AnalyticsPeriod
    currency: str
    filters: dict[str, str | None]
    dimension: str | None
    dimension_id: str | None
    reconciled_value: Decimal | None
    coverage: Coverage
    items: list[DrilldownItem]
    total: int
    page: int
    page_size: int
    pages: int
