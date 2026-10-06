"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentDetail, DocumentFieldCandidate } from "@/lib/types";

const fieldLabel = (value: string) => value.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");
const valueText = (value: unknown) => value === null || value === undefined || value === "" ? "—" : String(value);
const billSections = [
  { title: "B/L details", fields: ["bill_of_lading_number", "issue_date"] },
  { title: "Parties", fields: ["shipper_name", "shipper_registration_number", "shipper_vat_number", "consignee_name", "consignee_registration_number", "consignee_vat_number", "notify_party_name", "carrier_name"] },
  { title: "Transport", fields: ["vessel_name", "vessel_imo_number", "voyage_number", "port_of_loading", "port_of_discharge", "place_of_receipt", "place_of_delivery", "shipment_reference", "booking_reference"] },
  { title: "Cargo", fields: ["description_of_goods", "total_packages", "total_gross_weight", "measurement", "measurement_unit"] },
];

export function DocumentReview({ documentId }: { documentId: string }) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [selectedContainer, setSelectedContainer] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const result = await api.document<DocumentDetail>(documentId);
      setDetail(result);
      setEdits(Object.fromEntries(result.candidates.map((item) => [item.id, valueText(item.normalized_value) === "—" ? "" : valueText(item.normalized_value)])));
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the document.");
    }
  }, [documentId]);

  useEffect(() => { void load(); }, [load]);

  async function action(name: string, operation: () => Promise<unknown>) {
    setBusy(name); setError(null);
    try { await operation(); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Action failed."); }
    finally { setBusy(null); }
  }

  const groupedContainers = useMemo(() => {
    const groups = new Map<number, DocumentFieldCandidate[]>();
    for (const candidate of detail?.candidates ?? []) {
      if (candidate.group_type !== "container") continue;
      groups.set(candidate.group_index, [...(groups.get(candidate.group_index) ?? []), candidate]);
    }
    return [...groups.entries()].sort(([left], [right]) => left - right);
  }, [detail]);

  if (!detail) return <div className="panel emptyState"><strong>{error ?? "Loading document…"}</strong></div>;
  const record = detail.document;
  const editable = !["committed", "failed"].includes(record.status);
  const isBill = record.document_type === "BILL_OF_LADING";
  const documentCandidates = detail.candidates.filter((candidate) => candidate.group_type === "document");

  function saveCandidate(candidate: DocumentFieldCandidate) {
    const operation = candidate.group_type === "container"
      ? api.correctDocumentCandidate(documentId, candidate.id, edits[candidate.id])
      : api.correctDocumentField(documentId, candidate.field_name, edits[candidate.id]);
    return action(`candidate-${candidate.id}`, () => operation);
  }

  function candidateCard(candidate: DocumentFieldCandidate) {
    return <article className={`fieldCard ${candidate.status}`} key={candidate.id}>
      <div className="fieldMeta"><div><strong>{fieldLabel(candidate.field_name)}</strong><small>{candidate.extraction_method.replaceAll("_", " ")} · page {candidate.page_number ?? "—"}</small></div><span className={`confidence ${candidate.confidence >= .85 ? "high" : candidate.confidence >= .6 ? "medium" : "low"}`}>{Math.round(candidate.confidence * 100)}%</span></div>
      <div className="fieldValues"><div><span>Source</span><code>{valueText(candidate.raw_value)}</code></div><div><span>System</span><code>{valueText(candidate.system_normalized_value)}</code></div></div>
      <div className="fieldEdit"><input aria-label={`Correct ${fieldLabel(candidate.field_name)}`} disabled={!editable || !!busy} value={edits[candidate.id] ?? ""} onChange={(event) => setEdits((current) => ({ ...current, [candidate.id]: event.target.value }))}/><button disabled={!editable || !!busy || edits[candidate.id] === valueText(candidate.normalized_value)} onClick={() => saveCandidate(candidate)}>Save</button></div>
      {candidate.evidence && <blockquote>{candidate.evidence}</blockquote>}
      {candidate.match_method && <small className="matchNote">Canonical match: {candidate.match_method.replaceAll("_", " ")} ({Math.round((candidate.match_confidence ?? 0) * 100)}%)</small>}
    </article>;
  }

  return <div className="documentWorkbench">
    <div className="detailTopbar"><Link className="backLink" href="/documents">← Document history</Link><span className={`stateLabel ${record.status}`}>{record.status.replaceAll("_", " ")}</span></div>
    <div className="pageHeading detailHeading"><div><p className="eyebrow">{record.document_type.replaceAll("_", " ")} · {Math.round(record.classification_confidence * 100)}% classification</p><h1>{record.original_filename}</h1><p>{record.page_count} page{record.page_count === 1 ? "" : "s"} · {record.field_count} extracted fields · SHA-256 {record.checksum_sha256.slice(0, 16)}…</p></div><div className="buttonGroup">
      {record.document_type === "UNKNOWN" && <><button className="secondaryButton" disabled={!!busy} onClick={() => action("classify-invoice", () => api.classifyDocumentAs(documentId, "INVOICE"))}>Confirm invoice</button><button className="secondaryButton" disabled={!!busy} onClick={() => action("classify-bill", () => api.classifyDocumentAs(documentId, "BILL_OF_LADING"))}>Confirm B/L</button></>}
      <button className="secondaryButton" disabled={!!busy || !editable} onClick={() => action("validate", () => api.revalidateDocument(documentId))}>{busy === "validate" ? "Checking…" : "Revalidate"}</button>
      <button className="secondaryButton" disabled={!!busy || record.error_count > 0 || !["ready", "needs_review"].includes(record.status)} onClick={() => action("approve", () => api.approveDocument(documentId))}>{busy === "approve" ? "Approving…" : "Approve"}</button>
      <button className="primaryButton" disabled={!!busy || record.status !== "approved"} onClick={() => action("commit", () => api.commitDocument(documentId))}>{busy === "commit" ? "Committing…" : `Commit ${isBill ? "B/L" : "invoice"}`}</button>
    </div></div>
    {error && <div className="alert errorAlert"><strong>Could not continue</strong><span>{error}</span></div>}
    <div className="documentStats"><div><span>Extraction</span><strong>{record.extraction_method ?? "—"}</strong></div><div><span>Version</span><strong>{record.extraction_version ?? "—"}</strong></div><div><span>Review items</span><strong>{record.review_count}</strong></div><div><span>Blocking errors</span><strong>{record.error_count}</strong></div>{detail.canonical_invoice && <div><span>Canonical invoice</span><Link href="/invoices">{detail.canonical_invoice.invoice_number} →</Link></div>}{detail.canonical_bill_of_lading && <div><span>Canonical B/L</span><Link href={`/bills-of-lading/${detail.canonical_bill_of_lading.id}`}>{detail.canonical_bill_of_lading.number} →</Link></div>}</div>
    <div className="documentSplit">
      <section className="pdfPanel panel"><div className="panelHeading"><div><h2>Source PDF</h2><p>Original file retained as immutable review evidence.</p></div><a className="rowLink" href={api.documentSource(documentId, false)}>Download</a></div><iframe title={`Source PDF ${record.original_filename}`} src={api.documentSource(documentId)}/></section>
      <section className="panel fieldPanel"><div className="panelHeading"><div><h2>{isBill ? "Bill of Lading review" : "Extracted fields"}</h2><p>System values remain visible after corrections.</p></div><span className="secureNote">Human-in-the-loop</span></div>
        {detail.issues.length > 0 && <div className="documentIssues">{detail.issues.map((issue) => <div className={`issueCard ${issue.severity.toLowerCase()}`} key={issue.id}><strong>{issue.code}</strong><span>{issue.field ? `${issue.field}: ` : ""}{issue.message}</span></div>)}</div>}
        <div className="fieldList">
          {isBill ? billSections.map((section) => { const fields = documentCandidates.filter((candidate) => section.fields.includes(candidate.field_name)); return fields.length ? <section className="candidateSection" key={section.title}><h3>{section.title}</h3>{fields.map(candidateCard)}</section> : null; }) : documentCandidates.map(candidateCard)}
          {isBill && groupedContainers.length > 0 && <section className="candidateSection containerSection"><h3>Containers</h3><div className="containerReviewTable"><table className="dataTable"><thead><tr><th>Container</th><th>Type</th><th>Seal</th><th>Packages</th><th>Weight</th><th>Status</th></tr></thead><tbody>{groupedContainers.map(([index, candidates]) => { const byField = Object.fromEntries(candidates.map((candidate) => [candidate.field_name, candidate])); const needsReview = candidates.some((candidate) => candidate.status !== "ready"); return <tr className={selectedContainer === index ? "selectedContainer" : ""} key={index} onClick={() => setSelectedContainer(index)}><td><code>{valueText(byField.container_number?.normalized_value)}</code></td><td>{valueText(byField.container_size_type?.normalized_value)}</td><td>{valueText(byField.seal_number?.normalized_value)}</td><td>{valueText(byField.package_count?.normalized_value)}</td><td>{valueText(byField.gross_weight?.normalized_value)} kg</td><td><span className={`stateLabel ${needsReview ? "needs_review" : "ready"}`}>{needsReview ? "Review" : "Ready"}</span></td></tr>; })}</tbody></table></div><div className="selectedContainerFields">{(groupedContainers.find(([index]) => index === selectedContainer)?.[1] ?? groupedContainers[0][1]).map(candidateCard)}</div></section>}
        </div>
      </section>
    </div>
    <section className="panel auditPanel"><div className="panelHeading"><div><h2>Audit history</h2><p>Reviewer changes never overwrite the system-extracted baseline.</p></div></div>{detail.corrections.length ? <div className="auditList">{detail.corrections.map((item) => <div className="auditItem" key={item.id}><span className="auditDot"/><div><strong>{fieldLabel(item.field_name)}</strong><p>{valueText(item.previous_value)} → {valueText(item.corrected_value)}</p><small>{item.reviewer_reference ?? "Reviewer"} · {new Date(item.created_at).toLocaleString()}</small></div></div>)}</div> : <p className="emptyAudit">No reviewer corrections yet.</p>}</section>
  </div>;
}
