import Link from "next/link";

export default function OverviewPage() {
  return (
    <section>
      <div className="pageHeading"><div><p className="eyebrow">Operational data foundation</p><h1>Overview</h1><p>Turn fragmented logistics files into trusted canonical records.</p></div></div>
      <div className="heroCard">
        <div><span className="pill success">Foundation ready</span><h2>Your logistics data, made dependable.</h2><p>Analyze Excel and CSV structure, review mappings, validate every row, then commit only trusted records.</p><Link className="primaryButton" href="/data">Start an import <span>→</span></Link></div>
        <div className="flowDiagram"><span>Raw files</span><b>→</b><span>Input engine</span><b>→</b><span>Canonical data</span><b>→</b><span>Intelligence</span></div>
      </div>
      <div className="cardGrid">
        <article className="card"><span className="cardIcon">↥</span><h3>Universal Input</h3><p>Deterministic parsing and mapping with explicit human review.</p><Link href="/data">Import data →</Link></article>
        <article className="card"><span className="cardIcon">▤</span><h3>Canonical Shipments</h3><p>One tenant-scoped operational layer with source lineage.</p><Link href="/shipments">View shipments →</Link></article>
        <article className="card mutedCard"><span className="cardIcon">✦</span><h3>Intelligence modules</h3><p>Analytics, AI explanations, simulation, and automation build on validated data.</p><span className="quiet">Coming later</span></article>
      </div>
    </section>
  );
}
