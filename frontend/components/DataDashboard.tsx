"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DataQualitySummary, ImportHistoryPage } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  analyzed: "Uploaded",
  mapped: "Mapped",
  validated: "Ready",
  needs_review: "Needs review",
  partially_committed: "Partially committed",
  committed: "Complete",
  failed: "Failed",
};

export function DataDashboard() {
  const [quality, setQuality] = useState<DataQualitySummary | null>(null);
  const [history, setHistory] = useState<ImportHistoryPage | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.quality<DataQualitySummary>(),
      api.history<ImportHistoryPage>(search, status, page),
    ]).then(([qualityResult, historyResult]) => {
      setQuality(qualityResult);
      setHistory(historyResult);
      setError(null);
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load data quality."));
  }, [search, status, page]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setSearch(query);
  }

  return (
    <div className="dataOverview">
      <section>
        <div className="sectionHeading"><div><p className="eyebrow">Data quality</p><h2>Ingestion health</h2></div><span className="quiet">Validated rows across all imports</span></div>
        {error && <div className="alert errorAlert"><strong>Dashboard unavailable</strong><span>{error}</span></div>}
        <div className="qualityGrid">
          <article className="qualityHero"><div><strong>{quality?.ready_percent ?? 0}%</strong><span>Ready or committed</span></div><div className="qualityBar"><i style={{ width: `${quality?.ready_percent ?? 0}%` }}/></div><p>{quality?.total_evaluated_rows ?? 0} evaluated rows</p></article>
          <article className="qualityCard warningTone"><strong>{quality?.review_rows ?? 0}</strong><span>Rows need review</span><small>{quality?.review_percent ?? 0}% of evaluated data</small></article>
          <article className="qualityCard errorTone"><strong>{quality?.invalid_rows ?? 0}</strong><span>Invalid rows</span><small>Cannot be committed</small></article>
          <article className="qualityCard attentionTone"><strong>{quality?.imports_requiring_review ?? 0}</strong><span>Imports need attention</span><small>{quality?.unresolved_issues ?? 0} unresolved rows</small></article>
          <article className="qualityCard successTone"><strong>{quality?.recent_successful_imports ?? 0}</strong><span>Completed recently</span><small>{quality?.recent_failed_imports ?? 0} failed in 30 days</small></article>
        </div>
        <div className="documentQualityGrid">
          <article className="qualityCard warningTone"><strong>{quality?.documents_awaiting_review ?? 0}</strong><span>Documents need review</span><small>Awaiting a human decision</small></article>
          <article className="qualityCard attentionTone"><strong>{quality?.unresolved_document_fields ?? 0}</strong><span>Unresolved fields</span><small>Low-confidence or invalid candidates</small></article>
          <article className="qualityCard errorTone"><strong>{quality?.failed_document_processing ?? 0}</strong><span>Processing failures</span><small>Fail-closed documents</small></article>
          <article className="qualityCard successTone"><strong>{quality?.recent_processed_documents ?? 0}</strong><span>Documents processed</span><small>Last 30 days</small></article>
        </div>
      </section>

      <section className="panel widePanel historyPanel">
        <div className="panelHeading"><div><h2>Import history</h2><p>Open an import to review exceptions, corrections, and commit state.</p></div><span className="recordCount">{history?.total ?? 0} imports</span></div>
        <div className="historyFilters"><form className="searchBox" onSubmit={submit}><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search filename…"/><button>Search</button></form><select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="">All statuses</option><option value="needs_review">Needs review</option><option value="partially_committed">Partially committed</option><option value="validated">Ready</option><option value="committed">Complete</option><option value="failed">Failed</option></select></div>
        {history?.items.length ? <div className="tableWrap"><table className="dataTable historyTable"><thead><tr><th>Import</th><th>File</th><th>Date</th><th>Rows</th><th>Ready</th><th>Review</th><th>Invalid</th><th>Committed</th><th>Status</th><th/></tr></thead><tbody>{history.items.map((item, index) => <tr key={item.id}><td><code>IMP-{String(history.total - ((history.page - 1) * history.page_size + index)).padStart(3, "0")}</code></td><td><strong>{item.filename}</strong><small>{item.source_type.toUpperCase()}{item.selected_sheet ? ` · ${item.selected_sheet}` : ""}</small></td><td>{new Date(item.created_at).toLocaleDateString()}<small>{new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small></td><td>{item.detected_row_count}</td><td>{item.ready_count}</td><td>{item.review_count}</td><td>{item.rejected_count}</td><td>{item.imported_count}</td><td><span className={`stateLabel ${item.status}`}>{STATUS_LABELS[item.status] ?? item.status}</span></td><td><Link className="rowLink" href={`/data/imports/${item.id}`}>Open →</Link></td></tr>)}</tbody></table></div> : <div className="emptyState compact"><strong>No imports found</strong><p>Upload a file above to create the first auditable import.</p></div>}
        {history && history.pages > 1 && <div className="pagination"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page} of {history.pages}</span><button disabled={page >= history.pages} onClick={() => setPage((value) => value + 1)}>Next →</button></div>}
      </section>
    </div>
  );
}
