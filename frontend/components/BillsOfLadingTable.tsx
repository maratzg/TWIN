"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BillOfLadingPage } from "@/lib/types";

export function BillsOfLadingTable() {
  const [result, setResult] = useState<BillOfLadingPage | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.billsOfLading<BillOfLadingPage>(search, page).then((data) => { setResult(data); setError(null); }).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load Bills of Lading."));
  }, [search, page]);

  function submit(event: FormEvent) { event.preventDefault(); setPage(1); setSearch(query); }

  return <section className="panel widePanel">
    <div className="toolbar"><form className="searchBox" onSubmit={submit}><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search B/L, party, or carrier…"/><button>Search</button></form><span className="recordCount">{result?.total ?? 0} canonical B/L records</span></div>
    {error && <div className="alert errorAlert"><strong>Bills of Lading unavailable</strong><span>{error}</span></div>}
    {result?.items.length ? <div className="tableWrap"><table className="dataTable billsTable"><thead><tr><th>B/L</th><th>Shipment</th><th>Shipper / consignee</th><th>Vessel / voyage</th><th>POL → POD</th><th>Containers</th><th>Total weight</th><th>Issue date</th><th>Provenance</th></tr></thead><tbody>{result.items.map((bill) => <tr key={bill.id}><td><Link className="rowLink" href={`/bills-of-lading/${bill.id}`}>{bill.number} →</Link></td><td><Link className="rowLink" href={`/shipments/${bill.shipment_id}`}>{bill.shipment_reference ?? "Open shipment"} →</Link></td><td>{bill.shipper ?? "—"}<small>{bill.consignee ?? "—"}</small></td><td>{bill.vessel ?? "—"}<small>{bill.voyage ?? "—"}</small></td><td>{bill.port_of_loading ?? "—"}<small>→ {bill.port_of_discharge ?? "—"}</small></td><td>{bill.containers.length}</td><td>{bill.total_gross_weight ? `${bill.total_gross_weight} kg` : "—"}</td><td>{bill.issue_date ?? "—"}</td><td>{bill.source_document_id ? <Link className="rowLink" href={`/documents/${bill.source_document_id}`}>Source PDF →</Link> : "Legacy record"}</td></tr>)}</tbody></table></div> : <div className="emptyState"><span className="emptyIcon">▧</span><strong>No canonical Bills of Lading yet</strong><p>Approved B/L documents appear here after commit.</p><Link className="primaryButton" href="/documents">Review documents</Link></div>}
    {result && result.pages > 1 && <div className="pagination"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {page} of {result.pages}</span><button disabled={page >= result.pages} onClick={() => setPage((value) => value + 1)}>Next →</button></div>}
  </section>;
}
