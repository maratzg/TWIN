from datetime import date
from typing import Annotated
import uuid

from fastapi import APIRouter, HTTPException, Query

from app.analytics.query import AnalyticsFilters
from app.analytics.service import AnalyticsService
from app.api.deps import CurrentCompany, DatabaseSession
from app.schemas.analytics import (
    AnalyticsOptionsResponse,
    AnalyticsSummaryResponse,
    BreakdownResponse,
    DrilldownResponse,
    InsightsResponse,
    MetricRegistryResponse,
    TimeseriesResponse,
)


router = APIRouter(prefix="/analytics", tags=["analytics"])


def _metrics(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))


def _filters(
    customer_id: uuid.UUID | None,
    route: str | None,
    pol_id: uuid.UUID | None,
    pod_id: uuid.UUID | None,
    vessel_id: uuid.UUID | None,
    voyage_id: uuid.UUID | None,
) -> AnalyticsFilters:
    return AnalyticsFilters(
        customer_id=customer_id,
        route=route,
        pol_id=pol_id,
        pod_id=pod_id,
        vessel_id=vessel_id,
        voyage_id=voyage_id,
    )


def _execute(operation):
    try:
        return operation()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/metrics", response_model=MetricRegistryResponse)
def metrics(session: DatabaseSession, company: CurrentCompany) -> dict:
    return AnalyticsService(session, company).registry()


@router.get("/options", response_model=AnalyticsOptionsResponse)
def options(session: DatabaseSession, company: CurrentCompany) -> dict:
    return AnalyticsService(session, company).options()


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def summary(
    session: DatabaseSession,
    company: CurrentCompany,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    currency: str | None = None,
    metrics: str | None = None,
    customer_id: uuid.UUID | None = None,
    route: str | None = None,
    pol_id: uuid.UUID | None = None,
    pod_id: uuid.UUID | None = None,
    vessel_id: uuid.UUID | None = None,
    voyage_id: uuid.UUID | None = None,
) -> dict:
    return _execute(
        lambda: AnalyticsService(session, company).summary(
            from_date,
            to_date,
            currency,
            _filters(customer_id, route, pol_id, pod_id, vessel_id, voyage_id),
            _metrics(metrics) if metrics else None,
        )
    )


@router.get("/timeseries", response_model=TimeseriesResponse)
def timeseries(
    session: DatabaseSession,
    company: CurrentCompany,
    metrics: str = "revenue,cost,contribution_profit",
    grain: str = "month",
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    currency: str | None = None,
    customer_id: uuid.UUID | None = None,
    route: str | None = None,
    pol_id: uuid.UUID | None = None,
    pod_id: uuid.UUID | None = None,
    vessel_id: uuid.UUID | None = None,
    voyage_id: uuid.UUID | None = None,
) -> dict:
    return _execute(
        lambda: AnalyticsService(session, company).timeseries(
            _metrics(metrics),
            from_date,
            to_date,
            grain,
            currency,
            _filters(customer_id, route, pol_id, pod_id, vessel_id, voyage_id),
        )
    )


@router.get("/breakdown", response_model=BreakdownResponse)
def breakdown(
    session: DatabaseSession,
    company: CurrentCompany,
    dimension: str = "route",
    metrics: str = "revenue,cost,contribution_profit,contribution_margin,teu",
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    currency: str | None = None,
    customer_id: uuid.UUID | None = None,
    route: str | None = None,
    pol_id: uuid.UUID | None = None,
    pod_id: uuid.UUID | None = None,
    vessel_id: uuid.UUID | None = None,
    voyage_id: uuid.UUID | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict:
    return _execute(
        lambda: AnalyticsService(session, company).breakdown(
            _metrics(metrics),
            dimension,
            from_date,
            to_date,
            currency,
            _filters(customer_id, route, pol_id, pod_id, vessel_id, voyage_id),
            sort_by,
            sort_order,
            page,
            page_size,
        )
    )


@router.get("/insights", response_model=InsightsResponse)
def insights(
    session: DatabaseSession,
    company: CurrentCompany,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    currency: str | None = None,
    baseline: str = "trailing_3_months",
    limit: Annotated[int, Query(ge=1, le=30)] = 12,
    customer_id: uuid.UUID | None = None,
    route: str | None = None,
    pol_id: uuid.UUID | None = None,
    pod_id: uuid.UUID | None = None,
    vessel_id: uuid.UUID | None = None,
    voyage_id: uuid.UUID | None = None,
) -> dict:
    return _execute(
        lambda: AnalyticsService(session, company).insights(
            from_date,
            to_date,
            currency,
            _filters(customer_id, route, pol_id, pod_id, vessel_id, voyage_id),
            baseline,
            limit,
        )
    )


@router.get("/drilldown", response_model=DrilldownResponse)
def drilldown(
    session: DatabaseSession,
    company: CurrentCompany,
    metric: str,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    currency: str | None = None,
    customer_id: uuid.UUID | None = None,
    route: str | None = None,
    pol_id: uuid.UUID | None = None,
    pod_id: uuid.UUID | None = None,
    vessel_id: uuid.UUID | None = None,
    voyage_id: uuid.UUID | None = None,
    dimension: str | None = None,
    dimension_id: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict:
    return _execute(
        lambda: AnalyticsService(session, company).drilldown(
            metric,
            from_date,
            to_date,
            currency,
            _filters(customer_id, route, pol_id, pod_id, vessel_id, voyage_id),
            dimension,
            dimension_id,
            page,
            page_size,
        )
    )
