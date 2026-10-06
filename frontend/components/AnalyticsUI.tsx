import Link from "next/link";
import type {
  AnalyticsCoverage,
  AnalyticsDrilldown,
  AnalyticsInsight,
  DecimalValue,
  MetricMetadata,
  TimeseriesPoint,
} from "@/lib/types";

export function numberValue(value: DecimalValue): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatMetricValue(
  value: DecimalValue,
  metric: Pick<MetricMetadata, "unit" | "decimals">,
  currency = "EUR",
): string {
  const numeric = numberValue(value);
  if (numeric === null) return "—";
  if (metric.unit === "currency" || metric.unit === "currency_per_teu") {
    const formatted = new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency,
      maximumFractionDigits: metric.decimals,
    }).format(numeric);
    return metric.unit === "currency_per_teu" ? `${formatted} / TEU` : formatted;
  }
  const formatted = new Intl.NumberFormat("en-GB", {
    maximumFractionDigits: metric.decimals,
  }).format(numeric);
  if (metric.unit === "percent") return `${formatted}%`;
  if (metric.unit === "kg") return `${formatted} kg`;
  if (metric.unit === "teu") return `${formatted} TEU`;
  if (metric.unit === "days") return `${formatted} days`;
  return formatted;
}

export function formatComparison(
  value: DecimalValue,
  changeType: string,
): string {
  const numeric = numberValue(value);
  if (numeric === null) return "No comparable baseline";
  const sign = numeric > 0 ? "+" : "";
  if (changeType === "percentage_points") return `${sign}${numeric.toFixed(1)} pp`;
  return `${sign}${numeric.toFixed(1)}%`;
}

export function CoverageIndicator({ coverage }: { coverage: AnalyticsCoverage }) {
  const percent = numberValue(coverage.percent);
  const width = Math.max(0, Math.min(100, percent ?? 0));
  return (
    <div className="coverageIndicator" title={coverage.warnings.join(" ") || coverage.label}>
      <div><span>{coverage.label}</span><strong>{percent === null ? "—" : `${percent.toFixed(0)}%`}</strong></div>
      <i><b style={{ width: `${width}%` }} /></i>
    </div>
  );
}

const chartColors = ["#2e63d4", "#d17b25", "#198b7d", "#7b62c8"];

export function MetricChart({
  title,
  points,
  metrics,
  currency,
}: {
  title: string;
  points: TimeseriesPoint[];
  metrics: MetricMetadata[];
  currency: string;
}) {
  const width = 760;
  const height = 225;
  const padding = 24;
  const values = points.flatMap((point) => metrics.map((metric) => numberValue(point.values[metric.key])).filter((value): value is number => value !== null));
  const maximum = Math.max(...values, 1);
  const minimum = Math.min(...values, 0);
  const range = maximum - minimum || 1;
  const x = (index: number) => padding + (points.length <= 1 ? 0 : index * (width - padding * 2) / (points.length - 1));
  const y = (value: number) => padding + (maximum - value) * (height - padding * 2) / range;
  return (
    <section className="panel analyticsChart">
      <div className="panelHeading"><div><h2>{title}</h2><p>Backend-calculated values; chart scaling is presentational only.</p></div></div>
      <div className="chartLegend">
        {metrics.map((metric, index) => <span key={metric.key}><i style={{ background: chartColors[index % chartColors.length] }} />{metric.display_name}</span>)}
      </div>
      {points.length ? <>
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
          <line x1={padding} x2={width - padding} y1={y(0)} y2={y(0)} className="chartZero" />
          {metrics.map((metric, metricIndex) => {
            const path = points.map((point, index) => {
              const value = numberValue(point.values[metric.key]);
              return value === null ? null : `${x(index)},${y(value)}`;
            }).filter(Boolean).join(" ");
            return path ? <polyline key={metric.key} points={path} fill="none" stroke={chartColors[metricIndex % chartColors.length]} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" /> : null;
          })}
        </svg>
        <div className="chartAxis">{points.map((point, index) => <span key={point.label} style={{ left: `${points.length <= 1 ? 0 : index * 100 / (points.length - 1)}%` }}>{point.label}</span>)}</div>
        <div className="chartLatest">Latest: {metrics.map((metric) => <strong key={metric.key}>{metric.display_name} {formatMetricValue(points.at(-1)?.values[metric.key] ?? null, metric, currency)}</strong>)}</div>
      </> : <div className="emptyState compact"><strong>No values in this period.</strong></div>}
    </section>
  );
}

export function InsightCard({
  insight,
  currency,
  onOpen,
}: {
  insight: AnalyticsInsight;
  currency: string;
  onOpen: (insight: AnalyticsInsight) => void;
}) {
  const unitByMetric: Record<string, string> = {
    contribution_margin: "percent",
    customer_concentration: "percent",
    route_concentration: "percent",
    average_payment_delay: "days",
    shipments: "count",
    containers: "count",
    loaded_containers: "count",
    empty_containers: "count",
    loaded_empty_ratio: "ratio",
    teu: "teu",
    gross_weight: "kg",
    revenue_per_teu: "currency_per_teu",
    cost_per_teu: "currency_per_teu",
    profit_per_teu: "currency_per_teu",
  };
  const unit = unitByMetric[insight.metric] ?? "currency";
  const metric = { unit, decimals: unit === "percent" ? 1 : 2 };
  return (
    <article className={`insightCard ${insight.severity}`}>
      <div><span className={`insightSeverity ${insight.severity}`}>{insight.severity}</span><small>{insight.type.replaceAll("_", " ")}</small></div>
      <h3>{insight.title}</h3>
      <strong>{insight.entity_label}</strong>
      <p>{formatMetricValue(insight.current_value, metric, currency)}{insight.baseline_value !== null ? ` vs ${formatMetricValue(insight.baseline_value, metric, currency)} baseline` : ""}</p>
      {insight.contributors.slice(0, 2).map((item) => <span className="insightContributor" key={item.metric}>{item.metric.replaceAll("_", " ")}: {formatComparison(item.change_type === "percentage_points" ? item.absolute_change : item.percentage_change, item.change_type)}</span>)}
      {insight.entity_type === "shipment" && insight.entity_id ? <Link className="rowLink" href={`/shipments/${insight.entity_id}`}>Open shipment →</Link> : <button className="textButton" onClick={() => onOpen(insight)}>View analysis →</button>}
    </article>
  );
}

export function DrilldownPanel({
  result,
  onClose,
}: {
  result: AnalyticsDrilldown;
  onClose: () => void;
}) {
  return (
    <section className="panel analyticsDrilldown">
      <div className="panelHeading"><div><p className="eyebrow">Explainability</p><h2>{result.metric.display_name} drill-down</h2><p>{result.total} canonical records reconcile to {formatMetricValue(result.reconciled_value, result.metric, result.currency)}.</p></div><button className="secondaryButton" onClick={onClose}>Close</button></div>
      <CoverageIndicator coverage={result.coverage} />
      <div className="tableWrap"><table className="dataTable"><thead><tr><th>Record</th><th>Date</th><th>Customer / party</th><th>Route</th><th>Revenue</th><th>Cost</th><th>TEU</th><th>Provenance</th></tr></thead><tbody>
        {result.items.map((item) => <tr key={item.record_id}><td>{item.shipment_id ? <Link className="rowLink" href={`/shipments/${item.shipment_id}`}>{item.label} →</Link> : <strong>{item.label}</strong>}<small>{item.record_type}</small></td><td>{item.record_date}</td><td>{item.customer ?? "—"}</td><td>{item.route ?? "—"}</td><td>{item.revenue === null ? "—" : formatMetricValue(item.revenue, { unit: "currency", decimals: 2 }, result.currency)}</td><td>{item.cost === null ? "—" : formatMetricValue(item.cost, { unit: "currency", decimals: 2 }, result.currency)}</td><td>{item.teu ?? "—"}</td><td><div className="provenanceLinks">{item.import_job_id && <Link className="rowLink" href={`/data/imports/${item.import_job_id}`}>Import row {item.source_row_number} →</Link>}{item.source_document_ids.map((id) => <Link className="rowLink" href={`/documents/${id}`} key={id}>Source document →</Link>)}</div></td></tr>)}
      </tbody></table></div>
      {result.pages > 1 && <p className="paginationNote">Showing page {result.page} of {result.pages}. Use Analytics for paginated exploration.</p>}
    </section>
  );
}
