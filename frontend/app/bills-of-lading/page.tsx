import { BillsOfLadingTable } from "@/components/BillsOfLadingTable";

export default function BillsOfLadingPage() {
  return <section><div className="pageHeading"><div><p className="eyebrow">Canonical logistics</p><h1>Bills of Lading</h1><p>Reviewed maritime documents connected to shipments, containers, vessels, voyages, and ports.</p></div></div><BillsOfLadingTable /></section>;
}
