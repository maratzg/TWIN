"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { InvoiceHistoryPage } from "@/lib/types";


export function InvoicesTable() {
  const [result, setResult] = useState<InvoiceHistoryPage | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.invoices<InvoiceHistoryPage>(search, page).then((data) => { setResult(data); setError(null); }).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load invoices."));
  }, [search, page]);

  function submit(event: FormEvent) { event.preventDefault(); setPage(1); setSearch(query); }

  return <section className="panel widePanel">
    <div className="toolbar"><form className="searchBox" onSubmit={submit}><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search invoice or party…"/><button>Search</button></form><span className="recordCount">{result?.total ?? 0} canonical invoices</span></div>
    {error && <div className="alert errorAlert"><strong>Invoices unavailable</strong><span>{error}</span></div>}
    {result?.items.length ? <div className="tableWrap"><table className="dataTable invoicesTable"><thead><tr><th>Invoice</th><th>Direction</th><th>External party</th><th>Invoice date</th><th>Due date</th><th>Subtotal</th><th>VAT</th><th>Total</th><th>Status</th><th>Provenance</th></tr></thead><tbody>{result.items.map((invoice) => <tr key={invoice.id}><td><strong>{invoice.invoice_number}</strong></td><td><span className="pill neutral">{invoice.direction}</span></td><td>{invoice.supplier_name ?? invoice.customer_name ?? "—"}</td><td>{invoice.invoice_date}</td><td>{invoice.due_date ?? "—"}</td><td>{invoice.subtotal} {invoice.currency}</td><td>{invoice.vat} {invoice.currency}</td><td><strong>{invoice.total} {invoice.currency}</strong></td><td><span className={`stateLabel ${invoice.status}`}>{invoice.status}</span></td><td>{invoice.source_document_id ? <Link className="rowLink" href={`/documents/${invoice.source_document_id}`}>Source PDF →</Link> : "Legacy record"}</td></tr>)}</tbody></table></div> : <div className="emptyState"><span className="emptyIcon">◇</span><strong>No canonical invoices yet</strong><p>Approved invoice documents appear here after commit.</p><Link className="primaryButton" href="/documents">Review documents</Link></div>}
    {result && result.pages > 1 && <div className="pagination"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page} of {result.pages}</span><button disabled={page >= result.pages} onClick={() => setPage((value) => value + 1)}>Next →</button></div>}
  </section>;
}

