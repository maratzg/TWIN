# Document Engine

## Purpose and scope

Milestone 3A introduced a reusable, local-first document pipeline. Milestone 3B extends the same pipeline with Bill of Lading support. The classifier deliberately returns `UNKNOWN` for unsupported or weakly identified files; receipts, purchase orders, bank statements, packing lists, and customs documents remain unsupported.

```text
PDF → validate/store → extract text → classify → extract candidates
    → normalize → match/validate → review/correct → approve → commit
```

HTTP routes are thin. `DocumentService` owns state transitions, orchestration, correction, validation, matching, approval, and canonical commit. Tenant-scoped repositories own queries. Processing is synchronous in 3A, but all work sits behind the service boundary so a future job worker can call the same operation.

## Parsing, OCR, and storage

`PDFParser` uses pypdf for embedded text. It emits `ExtractedPage` records with page number, text, text blocks, approximate coordinates, and extraction method. It rejects corrupt, encrypted, empty, and excessively complex page content with stable error codes.

Embedded text is preferred. If total usable text is below the configured threshold, the service calls `OCRProvider`. The default `UnavailableOCRProvider` returns `OCR_REQUIRED`; it never fabricates text or sends the PDF elsewhere. A future local OCR adapter implements `available` and `extract(pdf_path)` and returns the same page model.

`DocumentStorage` defines `put`, `read`, and `path`. `LocalDocumentStorage` uses an atomic write below a configured root and an opaque `company/document/checksum.pdf` key. Absolute keys and traversal outside the root are rejected. Production can substitute private S3-compatible or on-premises object storage without changing document business logic.

Uploads are limited to 20 MB by default and must have a `.pdf` extension, acceptable MIME type, non-empty bytes, and a PDF signature. Safe basenames are stored; raw filesystem paths are never exposed.

## Classification and extraction

`DocumentClassifier` scores invoice and B/L evidence independently. B/L classification requires combinations of heading/number, party, port, vessel/voyage, container/seal, and cargo signals; a container number alone is insufficient. It returns document type, rule confidence, method, and supporting signals. The configured threshold defaults to `0.75`. Outputs are `INVOICE`, `BILL_OF_LADING`, and `UNKNOWN`.

`DocumentExtractor` is the extension protocol. `InvoiceExtractor` uses deterministic labeled-field and adjacent label/value extraction. Supported candidates are:

- invoice number, invoice date, due date, and direction;
- supplier/customer name, registration number, and VAT number;
- currency, subtotal, VAT amount, total amount, and VAT rate;
- payment, purchase-order, shipment, booking, B/L, and bank references.

There is no external LLM dependency. A future semantic provider may implement the same extractor contract and emit the same evidence-bearing candidates, but its output remains subject to confidence, deterministic normalization/validation, and human approval.

`BillOfLadingExtractor` implements the same protocol. It extracts B/L identity, parties, vessel/voyage, route, operational references, cargo totals, and repeating container groups. Container fields use `group_type=container` and a stable zero-based `group_index`; this avoids flattening one-to-many data into synthetic field names and can support future repeating structures.

## Candidate evidence and confidence

Candidates do not become canonical truth on extraction. Each retains group identity, raw value, system-normalized value, effective value, confidence, extraction method, page, evidence, optional bounding box, and optional canonical match.

- `confidence >= DOCUMENT_HIGH_CONFIDENCE_THRESHOLD` (default `0.85`) is `ready`.
- A normalized lower-confidence candidate is `review`.
- A value that cannot be normalized is `error`.

These are rule scores, not statistical probabilities. The UI shows confidence, method, page, evidence, raw/system/effective values, and match method. A correction updates only the effective value and creates an append-only `DocumentCorrection`; it never replaces raw or system-normalized history.

## Normalization and validation

Normalization supports ISO and common European dates, US/European thousands and decimal separators, currency codes/symbols, percentages, identifiers, and VAT numbers. Financial values are normalized as decimal strings and committed through SQLAlchemy `Decimal`/`NUMERIC`; binary floating point is not used for money. Country prefixes are retained.

Validation is deterministic and produces structured issues. It checks:

- required invoice number, date, direction, currency, subtotal, VAT, and total;
- normalization failures and low-confidence fields;
- due date not before invoice date;
- non-negative amounts;
- `subtotal + VAT = total` within configurable tolerance (default `0.02`);
- three-letter currency shape;
- external party resolution or a sufficiently identified new-party candidate;
- duplicate canonical invoice identity;
- conflicting or unmatched operational references.

No total is auto-corrected. No VAT or accounting treatment is inferred. Warnings require explicit reviewer approval; errors block approval and commit.

B/L validation additionally checks normalized B/L identity, ISO 6346 structure/check digit, duplicate container occurrences, numeric/non-negative packages and weights, total versus container weight tolerance, POL/POD equality, duplicate B/L identity, unresolved shipment creation requirements, and conflicts with trusted canonical records. Size/type normalization derives TEU only for unambiguous types. Invalid container check digits are never silently repaired.

## Identity and reference matching

Direction is derived by comparing extracted parties with the current company's VAT number, registration number, then exact normalized name. If the company side is not determinable, direction remains unresolved.

Party matching is tenant-scoped and ordered: exact VAT, exact registration number, exact external reference, exact normalized name, then a conservative fuzzy name threshold with a separation requirement. Weak similarity never creates a confident match. A new supplier/customer can be created at commit only when a reviewed VAT or registration identifier is present; identifiers are rechecked transactionally before creation.

Shipment, booking, and B/L references use exact tenant-scoped identifiers. Multiple references resolving to different shipments create a warning. Unmatched references are retained and warn but do not independently block approval.

B/L matching uses exact identifiers first: UN/LOCODE then normalized port name; IMO then exact normalized vessel name; vessel plus voyage number; shipment/B/L/booking references; and container number only with a complete matching route/voyage. Container-only matches deliberately require transport agreement because physical container numbers are reusable over time. Unmatched high-quality ports, vessels, voyages, or shipments become explicit creation candidates that require human approval. Existing canonical conflicts are errors and no trusted field is overwritten.

## States and review workflow

```text
uploaded → extracting → classified → extracted → ready
                                  ↘ needs_review → approved → committed
                    any processing step → failed
```

`UNKNOWN` classification enters `needs_review` and can be explicitly confirmed as an invoice. Validation moves an extracted document to `ready` when no issues exist, otherwise `needs_review`. Corrections clear prior approval and immediately revalidate. Reviewers can revalidate without re-uploading, approve only when there are no errors, and commit only an approved document. Repeated commit of the same source returns the already-linked invoice.

Canonical provenance is:

```text
Invoice.source_document_id
  → SourceDocument
  → DocumentFieldCandidate
  → page + evidence
  → retained source PDF
```

The B/L graph retains `BillOfLading.source_document_id`; document-created `Container` occurrences retain both the source document and `container:n` group key. The canonical commit runs as one database transaction and rolls back the whole graph on failure.

## APIs and UI

- `POST /api/v1/documents` — validate, store, and synchronously process a PDF
- `GET /api/v1/documents` — paginated filename/status/type history
- `GET /api/v1/documents/{id}` — metadata, pages, candidates, issues, corrections, and canonical link
- `GET /api/v1/documents/{id}/source` — authorized inline preview/download
- `PATCH /api/v1/documents/{id}/classification` — human invoice confirmation
- `PATCH /api/v1/documents/{id}/fields/{field}` — append correction and revalidate
- `PATCH /api/v1/documents/{id}/candidates/{candidate_id}` — correct a repeating candidate and revalidate
- `POST /api/v1/documents/{id}/revalidate` — rerun matching and validation
- `POST /api/v1/documents/{id}/approve` — explicit error-free approval
- `POST /api/v1/documents/{id}/commit` — idempotent canonical invoice creation
- `GET /api/v1/documents/{id}/issues` — structured current findings
- `GET /api/v1/invoices` and `/{id}` — tenant-scoped canonical invoice queries
- `GET /api/v1/bills-of-lading` and `/{id}` — tenant-scoped canonical B/L graph queries
- `GET /api/v1/shipments/{id}` — connected shipment detail with documents, containers, and invoices

The Data upload accepts PDF beside CSV/XLSX. Documents provides history and invoice/B/L filters. The workbench presents the PDF beside type-specific sections, evidence, correction, revalidation, approval, and commit. Repeating containers appear as a selectable table with per-field evidence and corrections. Canonical Invoice, B/L, and Shipment views retain source links. Data Quality includes document review, failure, unresolved-field, and recent-processing counts.

## Security and privacy

Every metadata, source, candidate, issue, correction, match, and invoice query is company-scoped. Demo identity cannot select another company; production remains fail-closed until authentication/membership is configured. Uploaded PDFs are treated as untrusted data and are parsed, not executed. Logs contain IDs, states, counts, and error codes—not full extracted text.

Local processing is the default. No document or extracted content is transmitted to OpenAI or any other third party.

## Limitations

The deterministic extractors target labeled digital documents. Arbitrary carrier layouts, line items, handwritten fields, and accounting treatment remain outside scope. B/L container rows currently require recognizable delimited/table-like text order. Image-only PDFs require a configured OCR adapter. Bounding-box information is retained where practical, but the review UI uses page/evidence context rather than overlays. Port aliases are intentionally limited until governed reference data exists; ambiguous names remain unresolved rather than being guessed.
