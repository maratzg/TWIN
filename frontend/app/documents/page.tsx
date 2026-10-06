import { DocumentsList } from "@/components/DocumentsList";


export default function DocumentsPage() {
  return <section><div className="pageHeading"><div><p className="eyebrow">Document intelligence</p><h1>Documents</h1><p>Invoice PDFs moving through classification, extraction, validation, review, and commit.</p></div></div><DocumentsList /></section>;
}

