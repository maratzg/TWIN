import { InvoicesTable } from "@/components/InvoicesTable";


export default function InvoicesPage() {
  return <section><div className="pageHeading"><div><p className="eyebrow">Canonical finance</p><h1>Invoices</h1><p>Reviewed invoice records with immutable source-document provenance.</p></div></div><InvoicesTable /></section>;
}

