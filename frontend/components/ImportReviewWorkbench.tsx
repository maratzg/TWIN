"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { CommitSummary, ImportDetail, ImportRowDetail, ImportRowListItem, ImportRowPage, MappingResponse } from "@/lib/types";
import { RowReviewPanel } from "@/components/RowReviewPanel";

const fieldLabel = (value: string) => value.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
const STATUS_LABELS: Record<string, string> = { committed: "Complete", partially_committed: "Partially committed", needs_review: "Needs review", validated: "Ready", mapped: "Mapped", analyzed: "Uploaded" };
const statusLabel = (value: string) => STATUS_LABELS[value] ?? value.replaceAll("_", " ");

export function ImportReviewWorkbench({ importId }: { importId: string }) {
  const [detail, setDetail] = useState<ImportDetail | null>(null);
  const [rows, setRows] = useState<ImportRowPage | null>(null);
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [activeRow, setActiveRow] = useState<ImportRowDetail | null>(null);
  const [mappingDrafts, setMappingDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const [detailResult, rowResult] = await Promise.all([
      api.importDetail<ImportDetail>(importId),
      api.importRows<ImportRowPage>(importId, filter, page),
    ]);
    setDetail(detailResult); setRows(rowResult);
    setMappingDrafts(Object.fromEntries(detailResult.mappings.map((item) => [item.source_column, item.canonical_field ?? ""])));
  }

  useEffect(() => {
    load().catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load import."));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [importId, filter, page]);

  const issueRows = useMemo(() => rows?.items.filter((row) => row.issue_count > 0) ?? [], [rows]);

  async function openRow(rowId: string) {
    setError(null);
    try { setActiveRow(await api.rowDetail<ImportRowDetail>(importId, rowId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not open row."); }
  }

  async function runAction(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(null); setNotice(null);
    try { await action(); setNotice(success); setSelected(new Set()); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Action failed."); }
    finally { setBusy(false); }
  }

  async function runCommit(rowIds?: string[]) {
    setBusy(true); setError(null); setNotice(null);
    try {
      const result = await api.commit<CommitSummary>(importId, rowIds);
      const skippedReasons = [...new Set(result.skipped.map((item) => item.reason))];
      const skipped = result.skipped.length
        ? ` ${result.skipped.length} skipped (${skippedReasons.join(", ")}).`
        : "";
      setNotice(`${result.committed} row${result.committed === 1 ? "" : "s"} committed.${skipped}`);
      setSelected(new Set());
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Commit failed.");
    } finally { setBusy(false); }
  }

  async function applyMapping(sourceColumn: string) {
    const canonicalField = mappingDrafts[sourceColumn];
    if (!canonicalField) return;
    await runAction(
      () => api.saveMapping<MappingResponse>(importId, [{ source_column: sourceColumn, canonical_field: canonicalField, user_confirmed: true }], true),
      `${sourceColumn} now maps to ${fieldLabel(canonicalField)}. All uncommitted rows were reprocessed.`,
    );
  }

  function toggle(rowId: string) {
    setSelected((current) => { const next = new Set(current); if (next.has(rowId)) next.delete(rowId); else next.add(rowId); return next; });
  }

  function moveIssue(direction: -1 | 1) {
    if (!activeRow) return;
    const index = issueRows.findIndex((row) => row.id === activeRow.id);
    const target = issueRows[index + direction];
    if (target) openRow(target.id);
  }

  if (!detail || !rows) return <div className="emptyState"><strong>Loading import workbench…</strong></div>;
  const countFor = (value: string) => value === "all" ? detail.detected_row_count : value === "ready" ? detail.ready_count : value === "review" ? detail.review_count : value === "invalid" ? detail.rejected_count : detail.imported_count;
  const canChangeMapping = detail.imported_count === 0;

  return (
    <div className="workbench">
      <div className="detailTopbar"><Link href="/data" className="backLink">← Data / Import</Link><span className={`stateLabel ${detail.status}`}>{statusLabel(detail.status)}</span></div>
      <div className="pageHeading detailHeading"><div><p className="eyebrow">Import review</p><h1>{detail.filename}</h1><p>{detail.company_name} · Uploaded {new Date(detail.created_at).toLocaleString()}</p></div><button className="secondaryButton" disabled={busy} onClick={() => runAction(() => api.validate(importId), "Entire import revalidated.")}>Revalidate import</button></div>
      {error && <div className="alert errorAlert"><strong>Could not continue</strong><span>{error}</span></div>}{notice && <div className="alert successAlert"><strong>Updated</strong><span>{notice}</span></div>}

      <div className="importMetaGrid"><div><span>Source</span><strong>{detail.source_type.toUpperCase()}</strong><small>{detail.selected_sheet ?? "Single table"}</small></div><div><span>Rows detected</span><strong>{detail.detected_row_count}</strong><small>Header row {detail.header_row}</small></div><div><span>Mapping</span><strong>{detail.mapping_complete ? "Confirmed" : "Needs review"}</strong><small>{detail.mappings.filter((item) => item.user_confirmed).length} confirmed columns</small></div><div><span>Validation</span><strong>{detail.validation_complete ? "Current" : "Not run"}</strong><small>Deterministic rules</small></div><div><span>Committed</span><strong>{detail.imported_count}</strong><small>{detail.ready_count} still ready</small></div></div>
      <div className="summaryGrid workbenchSummary"><div className="summary ready"><strong>{detail.ready_count}</strong><span>Ready</span></div><div className="summary review"><strong>{detail.review_count}</strong><span>Needs review</span></div><div className="summary invalid"><strong>{detail.rejected_count}</strong><span>Invalid</span></div><div className="summary committedSummary"><strong>{detail.imported_count}</strong><span>Committed</span></div></div>

      <section className="panel widePanel mappingReview"><div className="panelHeading"><div><h2>Column mapping</h2><p>A mapping change affects every uncommitted row and is learned for this company.</p></div><span className="secureNote">Column-wide action</span></div><div className="mappingCards">{detail.mappings.map((mapping) => <div className={!mapping.canonical_field ? "mappingCard unresolved" : "mappingCard"} key={mapping.source_column}><div><code>{mapping.source_column}</code><small>{mapping.mapping_method.replaceAll("_", " ")} · {Math.round(mapping.confidence * 100)}%</small></div><select disabled={!canChangeMapping} value={mappingDrafts[mapping.source_column] ?? ""} onChange={(event) => setMappingDrafts((current) => ({ ...current, [mapping.source_column]: event.target.value }))}><option value="">Unmapped</option>{detail.canonical_fields.map((field) => <option value={field} key={field}>{fieldLabel(field)}</option>)}</select><button disabled={busy || !canChangeMapping || !mappingDrafts[mapping.source_column] || mappingDrafts[mapping.source_column] === (mapping.canonical_field ?? "")} onClick={() => applyMapping(mapping.source_column)}>Apply to all rows</button></div>)}</div>{!canChangeMapping && <div className="mappingLock">Mappings are locked because canonical rows have already been committed. Row corrections remain available for uncommitted rows.</div>}</section>

      <section className="panel widePanel rowWorkbench"><div className="panelHeading"><div><h2>Import rows</h2><p>Focus on exceptions, correct interpreted values, then selectively commit trusted records.</p></div><span className="recordCount">{selected.size} selected</span></div><div className="rowTabs">{[["all", "All"], ["ready", "Ready"], ["review", "Needs review"], ["invalid", "Invalid"], ["committed", "Committed"]].map(([value, label]) => <button className={filter === value ? "active" : ""} onClick={() => { setFilter(value); setPage(1); setSelected(new Set()); }} key={value}>{label}<span>{countFor(value)}</span></button>)}</div><div className="bulkBar"><div><button disabled={busy || selected.size === 0} onClick={() => runAction(() => api.approveRows(importId, [...selected]), `${selected.size} selected rows processed for approval.`)}>Approve selected ready</button><button disabled={busy || selected.size === 0} onClick={() => runAction(() => api.revalidateRows(importId, [...selected]), "Selected context revalidated against the full import.")}>Revalidate selected</button><button className="commitAction" disabled={busy || selected.size === 0} onClick={() => runCommit([...selected])}>Commit selected</button></div><button className="primaryButton" disabled={busy || detail.ready_count === 0} onClick={() => runCommit()}>Commit all {detail.ready_count} ready</button></div>
        <div className="tableWrap"><table className="dataTable reviewRowsTable"><thead><tr><th/><th>Source row</th><th>Reference</th><th>Customer</th><th>Container</th><th>Gross weight</th><th>Issues</th><th>Corrections</th><th>Status</th><th/></tr></thead><tbody>{rows.items.map((row) => <tr key={row.id} className={activeRow?.id === row.id ? "selectedRow" : ""}><td><input type="checkbox" checked={selected.has(row.id)} onChange={() => toggle(row.id)} aria-label={`Select row ${row.row_number}`}/></td><td><strong>#{row.row_number}</strong></td><td>{row.summary.reference ?? "—"}</td><td>{row.summary.customer ?? "—"}</td><td><code>{row.summary.container ?? "—"}</code></td><td>{row.summary.gross_weight ? `${row.summary.gross_weight} kg` : "—"}</td><td>{row.issue_codes.length ? <div className="issueCodes">{row.issue_codes.slice(0, 2).map((code) => <span key={code}>{code.replaceAll("_", " ")}</span>)}{row.issue_count > 2 && <small>+{row.issue_count - 2}</small>}</div> : <span className="quiet">None</span>}</td><td>{row.correction_count || "—"}</td><td><span className={`stateLabel ${row.disposition}`}>{row.disposition.replaceAll("_", " ")}</span></td><td><button className="rowLink" onClick={() => openRow(row.id)}>{row.issue_count ? "Review →" : "Inspect →"}</button></td></tr>)}</tbody></table></div>{rows.items.length === 0 && <div className="emptyState compact"><strong>No rows in this view</strong><p>Choose another status filter.</p></div>}{rows.pages > 1 && <div className="pagination"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page} of {rows.pages}</span><button disabled={page >= rows.pages} onClick={() => setPage((value) => value + 1)}>Next →</button></div>}</section>

      {activeRow && <RowReviewPanel importId={importId} detail={activeRow} onClose={() => setActiveRow(null)} onUpdated={(updated) => { setActiveRow(updated); load(); }} onPrevious={issueRows.findIndex((row) => row.id === activeRow.id) > 0 ? () => moveIssue(-1) : undefined} onNext={issueRows.findIndex((row) => row.id === activeRow.id) >= 0 && issueRows.findIndex((row) => row.id === activeRow.id) < issueRows.length - 1 ? () => moveIssue(1) : undefined}/>} 
    </div>
  );
}
