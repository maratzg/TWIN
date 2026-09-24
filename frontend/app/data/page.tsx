import { ImportWizard } from "@/components/ImportWizard";
import { DataDashboard } from "@/components/DataDashboard";

export default function DataPage() {
  return <section><div className="pageHeading"><div><p className="eyebrow">Universal Input Engine</p><h1>Data / Import</h1><p>Review ingestion quality, process exceptions, and preserve full lineage.</p></div></div><ImportWizard /><DataDashboard /></section>;
}
