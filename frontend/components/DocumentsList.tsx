"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { DocumentHistoryPage } from "@/lib/types";


export function DocumentsList() {
  const [history, setHistory] = useState<DocumentHistoryPage | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.documents<DocumentHistoryPage>(search, status, page, documentType)
      .then((result) => { setHistory(result); setError(null); })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load documents."));
  }, [search, status, page, documentType]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setPage(1);
    setSearch(query);
  }

  return <section className="panel widePanel historyPanel">
    <div className="panelHeading"><div><h2>Document history</h2><p>Every source, extraction candidate, correction, approval, and canonical commit stays linked.</p></div><span className="recordCount">{history?.total ?? 0} documents</span></div>
    {error && <div className="alert errorAlert"><strong>Documents unavailable</strong><span>{error}</span></div>}
    <div className="historyFilters">
      <form className="searchBox" onSubmit={submit}><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search filename…"/><button>Search</button></form>
      <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="">All statuses</option><option value="needs_review">Needs review</option><option value="ready">Ready</option><option value="approved">Approved</option><option value="committed">Committed</option><option value="failed">Failed</option></select>
      <select value={documentType} onChange={(event) => { setDocumentType(event.target.value); setPage(1); }}><option value="">All types</option><option value="INVOICE">Invoice</option><option value="BILL_OF_LADING">Bill of Lading</option><option value="UNKNOWN">Unknown</option></select>
    </div>
    {history?.items.length ? <div className="tableWrap"><table className="dataTable historyTable documentTable"><thead><tr><th>Document</th><th>Type</th><th>Uploaded</th><th>Pages</th><th>Fields</th><th>Review</th><th>Errors</th><th>Classification</th><th>Status</th><th>Canonical</th><th/></tr></thead><tbody>{history.items.map((item) => <tr key={item.id}>
      <td><strong>{item.original_filename}</strong><small>{(item.size_bytes / 1024).toFixed(1)} KB · {item.checksum_sha256.slice(0, 10)}…</small></td>
      <td>{item.document_type}</td><td>{new Date(item.created_at).toLocaleDateString()}<small>{new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small></td>
      <td>{item.page_count}</td><td>{item.field_count}<small>{item.ready_fields} ready</small></td><td>{item.review_count}</td><td>{item.error_count}</td>
      <td><span className={item.classification_confidence >= .85 ? "confidence high" : "confidence medium"}>{Math.round(item.classification_confidence * 100)}%</span></td>
      <td><span className={`stateLabel ${item.status}`}>{item.status.replaceAll("_", " ")}</span></td><td>{item.canonical_invoice_id ? <Link className="rowLink" href="/invoices">{item.canonical_invoice_number} →</Link> : item.canonical_bill_of_lading_id ? <Link className="rowLink" href={`/bills-of-lading/${item.canonical_bill_of_lading_id}`}>{item.canonical_bill_of_lading_number} →</Link> : "—"}</td><td><Link className="rowLink" href={`/documents/${item.id}`}>Review →</Link></td>
    </tr>)}</tbody></table></div> : <div className="emptyState"><span className="emptyIcon">□</span><strong>No documents found</strong><p>Upload an invoice or Bill of Lading PDF from Data / Import to start the review pipeline.</p><Link className="primaryButton" href="/data">Upload document</Link></div>}
    {history && history.pages > 1 && <div className="pagination"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page} of {history.pages}</span><button disabled={page >= history.pages} onClick={() => setPage((value) => value + 1)}>Next →</button></div>}
  </section>;
}
