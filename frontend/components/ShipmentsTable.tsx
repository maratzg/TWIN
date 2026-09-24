"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ShipmentPage } from "@/lib/types";

const empty = "—";

export function ShipmentsTable() {
  const [data, setData] = useState<ShipmentPage | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true); setError(null);
    api.shipments<ShipmentPage>(search, page)
      .then(setData)
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load shipments."))
      .finally(() => setLoading(false));
  }, [search, page]);

  function submit(event: FormEvent) {
    event.preventDefault();
    setPage(1); setSearch(query);
  }

  if (error) return <div className="alert errorAlert"><strong>Could not load shipments</strong><span>{error}</span></div>;
  return (
    <section className="panel widePanel">
      <div className="toolbar"><form className="searchBox" onSubmit={submit}><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search reference, customer, B/L, container…"/><button>Search</button></form><span className="recordCount">{data?.total ?? 0} records</span></div>
      {loading ? <div className="emptyState"><strong>Loading canonical records…</strong></div> : data && data.items.length ? <>
        <div className="tableWrap"><table className="dataTable shipmentsTable"><thead><tr><th>Reference</th><th>Customer</th><th>B/L</th><th>Container</th><th>Vessel / voyage</th><th>POL → POD</th><th>ETD / ETA</th><th>Weight / TEU</th><th>Revenue</th><th>Status</th></tr></thead><tbody>{data.items.map((shipment) => <tr key={shipment.id}>
          <td><strong>{shipment.reference ?? empty}</strong></td><td>{shipment.customer ?? empty}</td><td>{shipment.bill_of_lading ?? empty}</td><td><code>{shipment.container ?? empty}</code></td>
          <td>{shipment.vessel ?? empty}<small>{shipment.voyage ?? ""}</small></td><td>{shipment.port_of_loading ?? empty}<small>→ {shipment.port_of_discharge ?? empty}</small></td>
          <td>{shipment.etd ?? empty}<small>{shipment.eta ?? empty}</small></td><td>{shipment.gross_weight ? `${shipment.gross_weight} kg` : empty}<small>{shipment.teu ? `${shipment.teu} TEU` : ""}</small></td>
          <td>{shipment.revenue ? `${shipment.revenue} ${shipment.currency ?? ""}` : empty}</td><td><span className="pill neutral">{shipment.status ?? empty}</span></td>
        </tr>)}</tbody></table></div>
        <div className="pagination"><button disabled={data.page <= 1} onClick={() => setPage((value) => value - 1)}>← Previous</button><span>Page {data.page} of {data.pages}</span><button disabled={data.page >= data.pages} onClick={() => setPage((value) => value + 1)}>Next →</button></div>
      </> : <div className="emptyState"><span className="emptyIcon">▤</span><strong>No shipments yet</strong><p>Commit ready rows from Data / Import to populate the canonical shipment table.</p></div>}
    </section>
  );
}

