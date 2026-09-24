"use client";

import Link from "next/link";
import { ChangeEvent, DragEvent, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { CommitSummary, ImportAnalysis, MappingItem, MappingResponse, ValidationSummary } from "@/lib/types";

type Step = "upload" | "mapping" | "validation" | "complete";

const fieldLabel = (value: string) => value.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join(" ");

export function ImportWizard() {
  const [step, setStep] = useState<Step>("upload");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<ImportAnalysis | null>(null);
  const [canonicalFields, setCanonicalFields] = useState<string[]>([]);
  const [mappings, setMappings] = useState<MappingItem[]>([]);
  const [validation, setValidation] = useState<ValidationSummary | null>(null);
  const [result, setResult] = useState<CommitSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const progress = useMemo(() => ({ upload: 1, mapping: 2, validation: 3, complete: 4 })[step], [step]);

  function chooseFile(file: File | undefined) {
    if (!file) return;
    const suffix = file.name.split(".").pop()?.toLowerCase();
    if (suffix !== "csv" && suffix !== "xlsx") {
      setError("Choose a .csv or .xlsx file.");
      return;
    }
    setSelectedFile(file);
    setError(null);
  }

  async function analyze() {
    if (!selectedFile) return;
    setBusy(true); setError(null);
    try {
      const analyzed = await api.upload<ImportAnalysis>(selectedFile);
      const mapping = await api.getMapping<MappingResponse>(analyzed.id);
      setAnalysis(analyzed);
      setMappings(mapping.mappings);
      setCanonicalFields(mapping.canonical_fields);
      setStep("mapping");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Upload failed.");
    } finally { setBusy(false); }
  }

  function updateMapping(sourceColumn: string, canonicalField: string) {
    setMappings((current) => current.map((item) => item.source_column === sourceColumn ? {
      ...item,
      canonical_field: canonicalField || null,
      confidence: canonicalField ? 1 : 0,
      mapping_method: canonicalField ? "user_confirmed" : "user_unmapped",
      user_confirmed: true,
    } : item));
  }

  async function saveAndValidate() {
    if (!analysis) return;
    setBusy(true); setError(null);
    try {
      await api.saveMapping<MappingResponse>(analysis.id, mappings.map((item) => ({
        source_column: item.source_column,
        canonical_field: item.canonical_field,
        user_confirmed: true,
      })));
      const summary = await api.validate<ValidationSummary>(analysis.id);
      setValidation(summary);
      setStep("validation");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Validation failed.");
    } finally { setBusy(false); }
  }

  async function commit() {
    if (!analysis) return;
    setBusy(true); setError(null);
    try {
      setResult(await api.commit<CommitSummary>(analysis.id));
      setStep("complete");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Commit failed.");
    } finally { setBusy(false); }
  }

  function reset() {
    setStep("upload"); setSelectedFile(null); setAnalysis(null); setMappings([]);
    setValidation(null); setResult(null); setError(null);
  }

  return (
    <div>
      <div className="stepper">
        {["Upload", "Map columns", "Validate", "Complete"].map((label, index) => (
          <div className={progress >= index + 1 ? "step active" : "step"} key={label}>
            <span>{progress > index + 1 ? "✓" : index + 1}</span><small>{label}</small>
          </div>
        ))}
      </div>
      {error && <div className="alert errorAlert"><strong>Could not continue</strong><span>{error}</span></div>}

      {step === "upload" && (
        <section className="panel uploadPanel">
          <div className="panelHeading"><div><h2>Import operational data</h2><p>Upload a logistics workbook or delimited file. Nothing is committed until after review and validation.</p></div><span className="secureNote">◈ Auditable pipeline</span></div>
          <label className={selectedFile ? "dropzone selected" : "dropzone"}
            onDragOver={(event: DragEvent) => event.preventDefault()}
            onDrop={(event: DragEvent) => { event.preventDefault(); chooseFile(event.dataTransfer.files[0]); }}>
            <input type="file" accept=".csv,.xlsx" onChange={(event: ChangeEvent<HTMLInputElement>) => chooseFile(event.target.files?.[0])}/>
            <span className="uploadIcon">↥</span>
            {selectedFile ? <><strong>{selectedFile.name}</strong><p>{(selectedFile.size / 1024).toFixed(1)} KB · Ready to analyze</p></> : <><strong>Drop a file here, or browse</strong><p>Excel (.xlsx) and CSV up to 20 MB</p></>}
          </label>
          <div className="actionRow"><span className="quiet">Source values are retained for traceability.</span><button className="primaryButton" disabled={!selectedFile || busy} onClick={analyze}>{busy ? "Analyzing…" : "Analyze file"}</button></div>
        </section>
      )}

      {step === "mapping" && analysis && (
        <section className="panel widePanel">
          <div className="panelHeading"><div><h2>Review column mapping</h2><p>Confirm the engine’s proposals. Low-confidence fields remain unresolved until you decide.</p></div><button className="textButton" onClick={reset}>Start over</button></div>
          <div className="detectionGrid">
            <div><small>File</small><strong>{analysis.filename}</strong></div><div><small>Type</small><strong>{analysis.source_type.toUpperCase()}</strong></div>
            <div><small>Sheet</small><strong>{analysis.selected_sheet ?? "—"}</strong></div><div><small>Header row</small><strong>{analysis.header_row}</strong></div>
            <div><small>Rows</small><strong>{analysis.detected_row_count}</strong></div><div><small>Columns</small><strong>{mappings.length}</strong></div>
          </div>
          <div className="tableWrap"><table className="dataTable mappingTable"><thead><tr><th>Source column</th><th>Example values</th><th>Proposed field</th><th>Confidence</th><th>Method</th></tr></thead><tbody>
            {mappings.map((item) => <tr key={item.source_column} className={!item.canonical_field ? "attentionRow" : ""}>
              <td><code>{item.source_column}</code></td><td className="samples">{item.sample_values.join(", ") || "No sample"}</td>
              <td><select value={item.canonical_field ?? ""} onChange={(event) => updateMapping(item.source_column, event.target.value)}><option value="">Leave unmapped</option>{canonicalFields.map((field) => <option value={field} key={field}>{fieldLabel(field)}</option>)}</select></td>
              <td><span className={item.confidence >= .85 ? "confidence high" : item.confidence >= .6 ? "confidence medium" : "confidence low"}>{Math.round(item.confidence * 100)}%</span></td>
              <td><span className="method">{item.mapping_method.replaceAll("_", " ")}</span></td>
            </tr>)}
          </tbody></table></div>
          <div className="actionRow"><span className="quiet">Saving confirms these choices for this company.</span><button className="primaryButton" disabled={busy} onClick={saveAndValidate}>{busy ? "Validating…" : "Save mapping & validate"}</button></div>
        </section>
      )}

      {step === "validation" && validation && (
        <section className="panel widePanel">
          <div className="panelHeading"><div><h2>Validation result</h2><p>Only ready rows will enter the canonical data layer.</p></div><button className="textButton" onClick={() => setStep("mapping")}>Back to mapping</button></div>
          <div className="summaryGrid"><div className="summary ready"><strong>{validation.ready}</strong><span>Ready</span></div><div className="summary review"><strong>{validation.needs_review}</strong><span>Needs review</span></div><div className="summary invalid"><strong>{validation.invalid}</strong><span>Invalid</span></div></div>
          {validation.issues.length ? <div className="tableWrap"><table className="dataTable"><thead><tr><th>Row</th><th>Field</th><th>Severity</th><th>Code</th><th>Issue</th></tr></thead><tbody>{validation.issues.map((issue, index) => <tr key={`${issue.row}-${issue.code}-${index}`}><td>{issue.row ?? "—"}</td><td>{issue.field ? fieldLabel(issue.field) : "Record"}</td><td><span className={`severity ${issue.severity.toLowerCase()}`}>{issue.severity}</span></td><td><code>{issue.code}</code></td><td>{issue.message}</td></tr>)}</tbody></table></div> : <div className="emptyState compact"><strong>All rows passed validation</strong><p>No warnings or errors were found.</p></div>}
          <div className="actionRow"><span className="quiet">Open the workbench to correct exceptions or selectively commit.</span><div className="buttonGroup"><button className="secondaryButton" disabled={busy || validation.ready === 0} onClick={commit}>{busy ? "Committing…" : `Commit ${validation.ready} ready`}</button><Link className="primaryButton" href={`/data/imports/${validation.import_id}`}>Review exceptions →</Link></div></div>
        </section>
      )}

      {step === "complete" && result && (
        <section className="panel completePanel"><div className="completeIcon">✓</div><span className="pill success">Ready rows committed</span><h2>{result.imported} shipments imported</h2><p>Trusted canonical records are available now. Any unresolved rows remain fail-closed in the review workbench.</p><div className="resultLine"><span>{result.needs_review} require review</span><span>{result.rejected} invalid</span></div><div className="buttonGroup"><button className="secondaryButton" onClick={reset}>Import another file</button><Link className="secondaryButton" href={`/data/imports/${result.import_id}`}>Open review</Link><Link className="primaryButton" href="/shipments">View shipments →</Link></div></section>
      )}
    </div>
  );
}
