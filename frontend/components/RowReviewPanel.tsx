"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ImportRowDetail } from "@/lib/types";

const fieldLabel = (value: string) => value.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
const displayValue = (value: unknown) => value === null || value === undefined || value === "" ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);

type Props = {
  importId: string;
  detail: ImportRowDetail;
  onClose: () => void;
  onUpdated: (detail: ImportRowDetail) => void;
  onPrevious?: () => void;
  onNext?: () => void;
};

export function RowReviewPanel({ importId, detail, onClose, onUpdated, onPrevious, onNext }: Props) {
  const suggestedField = detail.issues.find((issue) => issue.field && detail.canonical_fields.includes(issue.field))?.field ?? "gross_weight";
  const [canonicalField, setCanonicalField] = useState(suggestedField);
  const [sourceColumn, setSourceColumn] = useState<string>("");
  const [correctedValue, setCorrectedValue] = useState("");
  const [unit, setUnit] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const issueField = detail.issues.find((issue) => issue.field && detail.canonical_fields.includes(issue.field))?.field;
    setCanonicalField(issueField ?? "gross_weight");
    setSourceColumn(detail.cells.find((cell) => cell.canonical_field === issueField)?.source_column ?? "");
    setCorrectedValue(""); setUnit(""); setReason(""); setError(null);
  }, [detail]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(null);
    try {
      const updated = await api.correctRow<ImportRowDetail>(importId, detail.id, {
        source_column: sourceColumn || null,
        canonical_field: canonicalField,
        corrected_value: correctedValue,
        unit: unit || null,
        reason: reason || null,
      });
      onUpdated(updated);
    } catch (reasonValue) {
      setError(reasonValue instanceof Error ? reasonValue.message : "Correction failed.");
    } finally { setBusy(false); }
  }

  async function revalidate() {
    setBusy(true); setError(null);
    try { onUpdated(await api.revalidateRow<ImportRowDetail>(importId, detail.id)); }
    catch (reasonValue) { setError(reasonValue instanceof Error ? reasonValue.message : "Revalidation failed."); }
    finally { setBusy(false); }
  }

  return (
    <aside className="reviewPanel">
      <div className="reviewPanelHeader"><div><p className="eyebrow">Source row {detail.row_number}</p><h2>Review interpreted data</h2><span className={`stateLabel ${detail.disposition}`}>{detail.disposition.replaceAll("_", " ")}</span></div><button className="iconButton" onClick={onClose} aria-label="Close row review">×</button></div>
      <div className="issueNavigator"><button disabled={!onPrevious} onClick={onPrevious}>← Previous issue</button><span>{detail.issues.length} current issue{detail.issues.length === 1 ? "" : "s"}</span><button disabled={!onNext} onClick={onNext}>Next issue →</button></div>
      {detail.issues.length > 0 && <div className="rowIssues">{detail.issues.map((issue, index) => <div className={`issueCard ${issue.severity.toLowerCase()}`} key={`${issue.code}-${index}`}><strong>{issue.code.replaceAll("_", " ")}</strong><span>{issue.message}</span></div>)}</div>}

      <div className="reviewSection"><div className="reviewSectionTitle"><h3>Source → interpreted values</h3><span>Raw values never change</span></div><div className="tableWrap"><table className="dataTable cellTable"><thead><tr><th>Source</th><th>Raw value</th><th>Canonical field</th><th>System value</th><th>Effective value</th><th>Status</th></tr></thead><tbody>{detail.cells.map((cell, index) => <tr key={`${cell.source_column}-${cell.canonical_field}-${index}`}><td><code>{cell.source_column ?? "Human correction"}</code></td><td className="rawValue">{displayValue(cell.raw_value)}</td><td>{cell.canonical_field ? fieldLabel(cell.canonical_field) : <span className="quiet">Unmapped</span>}</td><td>{displayValue(cell.system_normalized_value)}</td><td><strong>{displayValue(cell.normalized_value)}</strong></td><td><span className={`cellState ${cell.status}`}>{cell.status}</span></td></tr>)}</tbody></table></div></div>

      {detail.disposition !== "committed" && <form className="correctionForm" onSubmit={save}><div className="reviewSectionTitle"><div><h3>Correct this row value</h3><p>Changes the canonical candidate only; original source data is retained.</p></div></div>{error && <div className="alert errorAlert"><span>{error}</span></div>}<div className="formGrid"><label><span>Canonical field</span><select value={canonicalField} onChange={(event) => setCanonicalField(event.target.value)}>{detail.canonical_fields.map((field) => <option value={field} key={field}>{fieldLabel(field)}</option>)}</select></label><label><span>Source column</span><select value={sourceColumn} onChange={(event) => setSourceColumn(event.target.value)}><option value="">No source column</option>{detail.cells.filter((cell) => cell.source_column).map((cell) => <option value={cell.source_column!} key={cell.source_column!}>{cell.source_column}</option>)}</select></label><label className="wideField"><span>Corrected value</span><input required value={correctedValue} onChange={(event) => setCorrectedValue(event.target.value)} placeholder="Enter the trusted interpreted value"/></label><label><span>Unit, if applicable</span><select value={unit} onChange={(event) => setUnit(event.target.value)}><option value="">None</option><option value="kg">kg</option><option value="t">tonnes</option></select></label><label><span>Reason</span><input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Optional reviewer note"/></label></div><div className="inlineActions"><button type="button" className="secondaryButton" disabled={busy} onClick={revalidate}>Revalidate row</button><button className="primaryButton" disabled={busy || !correctedValue}>{busy ? "Saving…" : "Save correction & revalidate"}</button></div></form>}

      <div className="reviewSection auditSection"><div className="reviewSectionTitle"><h3>Correction audit trail</h3><span>{detail.corrections.length} changes</span></div>{detail.corrections.length ? <div className="auditList">{detail.corrections.map((correction) => <div className="auditItem" key={correction.id}><span className="auditDot"/><div><strong>{correction.canonical_field ? fieldLabel(correction.canonical_field) : correction.correction_type}</strong><p><code>{displayValue(correction.previous_value)}</code> → <code>{displayValue(correction.corrected_value)}</code>{correction.unit ? ` ${correction.unit}` : ""}</p><small>{new Date(correction.created_at).toLocaleString()} · {correction.reviewer_reference ?? "Unknown reviewer"}{correction.reason ? ` · ${correction.reason}` : ""}</small></div></div>)}</div> : <div className="emptyAudit">No human corrections have been recorded for this row.</div>}</div>
    </aside>
  );
}
