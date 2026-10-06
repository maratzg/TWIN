"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CoverageIndicator, DrilldownPanel, MetricChart, formatComparison, formatMetricValue } from "@/components/AnalyticsUI";
import { api } from "@/lib/api";
import type { AnalyticsBreakdown, AnalyticsDrilldown, AnalyticsOptions, AnalyticsTimeseries, BreakdownRow, MetricMetadata, MetricRegistry } from "@/lib/types";

type Filters = {
  from: string;
  to: string;
  currency: string;
  metric: string;
  grain: string;
  dimension: string;
  customer_id: string;
  route: string;
  pol_id: string;
  pod_id: string;
  vessel_id: string;
  voyage_id: string;
};

const initialFilters: Filters = { from: "", to: "", currency: "EUR", metric: "revenue", grain: "month", dimension: "customer", customer_id: "", route: "", pol_id: "", pod_id: "", vessel_id: "", voyage_id: "" };

function query(filters: Filters, includeWorkspace = true) {
  const params = new URLSearchParams({ from: filters.from, to: filters.to, currency: filters.currency });
  for (const key of ["customer_id", "route", "pol_id", "pod_id", "vessel_id", "voyage_id"] as const) if (filters[key]) params.set(key, filters[key]);
  if (includeWorkspace) {
    params.set("metrics", filters.metric);
    params.set("grain", filters.grain);
  }
  return params;
}

export function AnalyticsWorkspace() {
  const [registry, setRegistry] = useState<MetricRegistry | null>(null);
  const [options, setOptions] = useState<AnalyticsOptions | null>(null);
  const [draft, setDraft] = useState<Filters>(initialFilters);
  const [applied, setApplied] = useState<Filters | null>(null);
  const [timeseries, setTimeseries] = useState<AnalyticsTimeseries | null>(null);
  const [breakdown, setBreakdown] = useState<AnalyticsBreakdown | null>(null);
  const [drilldown, setDrilldown] = useState<AnalyticsDrilldown | null>(null);
  const [sortBy, setSortBy] = useState("revenue");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (filters: Filters, requestedPage = 1, requestedSort = filters.metric, requestedOrder = "desc") => {
    setLoading(true);
    setError("");
    const timeParams = query(filters);
    const breakdownParams = query(filters, false);
    const contextMetrics = Array.from(new Set([filters.metric, "revenue", "cost", "contribution_margin", "teu"]));
    breakdownParams.set("metrics", contextMetrics.join(","));
    breakdownParams.set("dimension", filters.dimension);
    breakdownParams.set("sort_by", contextMetrics.includes(requestedSort) ? requestedSort : filters.metric);
    breakdownParams.set("sort_order", requestedOrder);
    breakdownParams.set("page", String(requestedPage));
    breakdownParams.set("page_size", "20");
    try {
      const [timeResult, breakdownResult] = await Promise.all([
        api.analyticsTimeseries<AnalyticsTimeseries>(timeParams),
        api.analyticsBreakdown<AnalyticsBreakdown>(breakdownParams),
      ]);
      setTimeseries(timeResult);
      setBreakdown(breakdownResult);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load analytics.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    Promise.all([api.analyticsMetrics<MetricRegistry>(), api.analyticsOptions<AnalyticsOptions>()])
      .then(([metricRegistry, analyticsOptions]) => {
        setRegistry(metricRegistry);
        setOptions(analyticsOptions);
        const defaults = { ...initialFilters, from: analyticsOptions.default_period.from_date, to: analyticsOptions.default_period.to_date, currency: analyticsOptions.default_currency };
        setDraft(defaults);
        setApplied(defaults);
        setSortBy(defaults.metric);
        return load(defaults, 1, defaults.metric, "desc");
      })
      .catch((reason: Error) => { setError(reason.message); setLoading(false); });
  }, [load]);

  const selectedMetric = useMemo(() => registry?.metrics.find((item) => item.key === draft.metric), [registry, draft.metric]);

  function update<K extends keyof Filters>(key: K, value: Filters[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function apply() {
    setApplied(draft);
    setPage(1);
    setSortBy(draft.metric);
    setSortOrder("desc");
    setDrilldown(null);
    await load(draft, 1, draft.metric, "desc");
  }

  async function changePage(next: number) {
    if (!applied) return;
    setPage(next);
    await load(applied, next, sortBy, sortOrder);
  }

  async function changeSort(metric: string) {
    if (!applied) return;
    const order = sortBy === metric && sortOrder === "desc" ? "asc" : "desc";
    setSortBy(metric);
    setSortOrder(order);
    setPage(1);
    await load(applied, 1, metric, order);
  }

  async function openDrilldown(row: BreakdownRow) {
    if (!applied) return;
    const params = query(applied, false);
    params.set("metric", applied.metric);
    params.set("dimension", row.drilldown.dimension);
    params.set("dimension_id", row.drilldown.dimension_id);
    params.set("page_size", "25");
    try {
      setDrilldown(await api.analyticsDrilldown<AnalyticsDrilldown>(params));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load drill-down.");
    }
  }

  if (!registry || !options) return <div className="emptyState"><strong>{error || "Loading the analytics registry…"}</strong></div>;

  return (
    <section className="analyticsPage">
      <div className="pageHeading analyticsHeading"><div><p className="eyebrow">Governed metric workspace</p><h1>Analytics</h1><p>Every value is calculated by the backend and traceable to canonical records.</p></div></div>
      <section className="panel analyticsFilters">
        <div className="filterGrid">
          <label><span>From</span><input type="date" value={draft.from} onChange={(event) => update("from", event.target.value)} /></label>
          <label><span>To</span><input type="date" value={draft.to} onChange={(event) => update("to", event.target.value)} /></label>
          <label><span>Currency</span><select value={draft.currency} onChange={(event) => update("currency", event.target.value)}>{options.currencies.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <label><span>Metric</span><select value={draft.metric} onChange={(event) => update("metric", event.target.value)}>{registry.metrics.map((item) => <option key={item.key} value={item.key}>{item.display_name}</option>)}</select></label>
          <label><span>Time grain</span><select value={draft.grain} onChange={(event) => update("grain", event.target.value)}>{registry.time_grains.map((item) => <option key={item}>{item}</option>)}</select></label>
          <label><span>Break down by</span><select value={draft.dimension} onChange={(event) => update("dimension", event.target.value)}>{registry.dimensions.filter((item) => item !== "time" && (!selectedMetric || selectedMetric.supported_dimensions.includes(item))).map((item) => <option key={item}>{item}</option>)}</select></label>
          <label><span>Customer</span><select value={draft.customer_id} onChange={(event) => update("customer_id", event.target.value)}><option value="">All customers</option>{options.customers.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <label><span>Route</span><select value={draft.route} onChange={(event) => update("route", event.target.value)}><option value="">All routes</option>{options.routes.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <label><span>POL</span><select value={draft.pol_id} onChange={(event) => update("pol_id", event.target.value)}><option value="">All ports</option>{options.ports.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <label><span>POD</span><select value={draft.pod_id} onChange={(event) => update("pod_id", event.target.value)}><option value="">All ports</option>{options.ports.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <label><span>Vessel</span><select value={draft.vessel_id} onChange={(event) => update("vessel_id", event.target.value)}><option value="">All vessels</option>{options.vessels.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
          <label><span>Voyage</span><select value={draft.voyage_id} onChange={(event) => update("voyage_id", event.target.value)}><option value="">All voyages</option>{options.voyages.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        </div>
        <div className="filterActions"><p>{selectedMetric?.description}<small>{selectedMetric?.calculation} · date basis: {selectedMetric?.date_basis.replaceAll("_", " ")}</small></p><button className="primaryButton" onClick={apply} disabled={loading}>Apply filters</button></div>
      </section>

      {error && <div className="alert errorAlert">{error}</div>}
      {timeseries && <MetricChart title={`${timeseries.metrics[0].display_name} over time`} points={timeseries.points} metrics={timeseries.metrics} currency={timeseries.currency} />}

      {breakdown && <section className="panel breakdownPanel">
        <div className="panelHeading"><div><h2>Breakdown by {breakdown.dimension}</h2><p>{breakdown.total} canonical groups · click any row to inspect contributing records.</p></div>{loading && <span className="recordCount">Recalculating…</span>}</div>
        <div className="tableWrap"><table className="dataTable analyticsTable"><thead><tr><th>{breakdown.dimension}</th>{breakdown.metrics.map((metric) => <th key={metric.key}><button className="sortButton" onClick={() => changeSort(metric.key)}>{metric.display_name}{sortBy === metric.key ? (sortOrder === "desc" ? " ↓" : " ↑") : ""}</button></th>)}</tr></thead><tbody>
          {breakdown.rows.map((row) => <tr key={row.dimension_id} onClick={() => openDrilldown(row)}><td><button className="rowLink">{row.dimension_label} →</button></td>{breakdown.metrics.map((metric: MetricMetadata) => { const comparison = row.comparisons[metric.key]; return <td key={metric.key}><strong>{formatMetricValue(row.values[metric.key], metric, breakdown.currency)}</strong><small>{comparison ? formatComparison(comparison.change_type === "percentage_points" ? comparison.absolute_change : comparison.percentage_change, comparison.change_type) : "No baseline"}</small><CoverageIndicator coverage={row.coverage[metric.key]} /></td>; })}</tr>)}
        </tbody></table></div>
        {!breakdown.rows.length && <div className="emptyState compact"><strong>No groups match these filters.</strong></div>}
        <div className="pagination"><span>Page {breakdown.page} of {breakdown.pages}</span><button disabled={page <= 1 || loading} onClick={() => changePage(page - 1)}>Previous</button><button disabled={page >= breakdown.pages || loading} onClick={() => changePage(page + 1)}>Next</button></div>
      </section>}
      {drilldown && <DrilldownPanel result={drilldown} onClose={() => setDrilldown(null)} />}
    </section>
  );
}
