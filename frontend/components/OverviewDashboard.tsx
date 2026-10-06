"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { CoverageIndicator, DrilldownPanel, InsightCard, MetricChart, formatComparison, formatMetricValue } from "@/components/AnalyticsUI";
import { api } from "@/lib/api";
import type { AnalyticsDrilldown, AnalyticsInsight, AnalyticsInsights, AnalyticsSummary, AnalyticsTimeseries } from "@/lib/types";

const financialMetrics = "revenue,cost,contribution_profit";
const volumeMetrics = "shipments,teu";

export function OverviewDashboard() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [financial, setFinancial] = useState<AnalyticsTimeseries | null>(null);
  const [volume, setVolume] = useState<AnalyticsTimeseries | null>(null);
  const [insights, setInsights] = useState<AnalyticsInsights | null>(null);
  const [drilldown, setDrilldown] = useState<AnalyticsDrilldown | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const financialParams = new URLSearchParams({ metrics: financialMetrics, grain: "month" });
    const volumeParams = new URLSearchParams({ metrics: volumeMetrics, grain: "month" });
    Promise.all([
      api.analyticsSummary<AnalyticsSummary>(),
      api.analyticsTimeseries<AnalyticsTimeseries>(financialParams),
      api.analyticsTimeseries<AnalyticsTimeseries>(volumeParams),
      api.analyticsInsights<AnalyticsInsights>(),
    ]).then(([summaryResult, financialResult, volumeResult, insightResult]) => {
      setSummary(summaryResult);
      setFinancial(financialResult);
      setVolume(volumeResult);
      setInsights(insightResult);
    }).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  }, []);

  const periodLabel = useMemo(() => summary ? `${summary.period.from_date} – ${summary.period.to_date}` : "", [summary]);

  async function openDrilldown(metric: string, insight?: AnalyticsInsight) {
    if (!summary) return;
    const params = new URLSearchParams({
      metric,
      from: summary.period.from_date,
      to: summary.period.to_date,
      currency: summary.currency,
      page_size: "15",
    });
    const dimension = insight?.drilldown.dimension;
    const dimensionId = insight?.drilldown.dimension_id;
    if (dimension && dimensionId) {
      params.set("dimension", dimension);
      params.set("dimension_id", dimensionId);
    }
    try {
      setDrilldown(await api.analyticsDrilldown<AnalyticsDrilldown>(params));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load drill-down.");
    }
  }

  if (loading) return <div className="emptyState"><strong>Calculating deterministic analytics…</strong><p>Reconciling canonical shipments, costs, containers, invoices, and payments.</p></div>;
  if (error && !summary) return <div className="alert errorAlert"><strong>Analytics unavailable.</strong> {error}</div>;
  if (!summary || !financial || !volume || !insights) return null;

  return (
    <section className="analyticsPage">
      <div className="pageHeading analyticsHeading">
        <div><p className="eyebrow">Deterministic decision support</p><h1>Operational overview</h1><p>{periodLabel} · {summary.currency} · canonical records only</p></div>
        <Link className="primaryButton" href="/analytics">Explore analytics <span>→</span></Link>
      </div>
      {error && <div className="alert errorAlert">{error}</div>}

      <div className="kpiGrid">
        {summary.metrics.map((item) => (
          <button className="kpiCard" key={item.metric.key} onClick={() => openDrilldown(item.metric.key)}>
            <span>{item.metric.display_name}</span>
            <strong>{formatMetricValue(item.value, item.metric, summary.currency)}</strong>
            <small className={(Number(item.comparison?.absolute_change ?? 0) >= 0 ? "positive" : "negative")}>
              {item.comparison ? formatComparison(item.comparison.change_type === "percentage_points" ? item.comparison.absolute_change : item.comparison.percentage_change, item.comparison.change_type) : "No comparison"}
            </small>
            <CoverageIndicator coverage={item.coverage} />
          </button>
        ))}
      </div>

      <div className="analyticsChartsGrid">
        <MetricChart title="Financial trajectory" points={financial.points} metrics={financial.metrics} currency={summary.currency} />
        <MetricChart title="Operational volume" points={volume.points} metrics={volume.metrics} currency={summary.currency} />
      </div>

      <section className="analyticsSection">
        <div className="sectionHeading"><div><p className="eyebrow">Detected, not generated</p><h2>Management insights</h2></div><span className="recordCount">{insights.baseline_window.replaceAll("_", " ")} baseline · {insights.insights.length} signals</span></div>
        {insights.insights.length ? <div className="insightGrid">{insights.insights.map((insight) => <InsightCard key={insight.id} insight={insight} currency={insights.currency} onOpen={(selected) => openDrilldown(selected.metric, selected)} />)}</div> : <div className="panel emptyState compact"><strong>No configured threshold was crossed.</strong><p>This is a valid result, not a failed analysis.</p></div>}
      </section>

      {drilldown && <DrilldownPanel result={drilldown} onClose={() => setDrilldown(null)} />}
    </section>
  );
}
