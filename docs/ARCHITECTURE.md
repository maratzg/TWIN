# Architecture

## Scope and design

TWIN remains a modular monolith in Milestone 4A. Deterministic analytics consumes the canonical model built by the input and document paths; it does not parse source files or bypass validation and review.

```text
Browser (Next.js)
       │ typed REST
       ▼
FastAPI routes ── identity/company context
       │
       ▼
Application services
  ├── Universal Input Engine
  │     ├── parsers
  │     ├── mapping
  │     ├── normalization
  │     └── validation
  ├── Document Engine
  │     ├── PDF parser + page/block evidence
  │     ├── OCR provider boundary
  │     ├── deterministic classifier
  │     ├── document-type extractors
  │     ├── normalization + validation
  │     └── source storage adapter
  ├── import review and correction orchestration
  ├── document review and canonical invoice/Bill of Lading orchestration
  ├── Analytics Engine
  │     ├── governed metric registry
  │     ├── tenant-scoped fact queries
  │     ├── Decimal calculations + coverage
  │     ├── periods, comparisons, and baselines
  │     └── deterministic insight rules
  ├── tenant-scoped repositories
  └── canonical domain models
       │
       ▼
PostgreSQL (SQLite for isolated tests/smoke runs)
```

Routes translate HTTP to typed inputs and outputs. Services own workflow and transaction decisions. Repositories centralize tenant predicates. Both ingestion engines have no HTTP dependency. Document processing is synchronous behind `DocumentService`, so its public service boundary can later be invoked by a worker without moving extraction logic into routes.

## Analytics pipeline

```text
Canonical Shipment / Container / Cost / Invoice / Payment
  → tenant-scoped batched fact query
  → central metric definition + Decimal calculation
  → coverage and currency exclusions
  → previous-period comparison or non-overlapping baseline
  → structured insight rules
  → typed summary / time-series / breakdown / drill-down APIs
  → presentational charts and tables
```

`AnalyticsService` is the application boundary. `AnalyticsQueryRepository` builds bounded in-memory facts with eager, tenant-scoped relationship queries; `MetricCalculator` applies the definitions in the registry; comparison and time modules own reusable period semantics; `InsightEngine` evaluates configured thresholds and emits evidence, contributors, stable IDs, and drill-down coordinates. The frontend formats returned values but does not recalculate business KPIs.

Analytics uses the transactional canonical database for this milestone. Query-oriented composite indexes support its primary predicates. No aggregate table or cache is introduced because the demo/company scale does not justify duplicated truth; a future projection can preserve the same service contracts.

## Document pipeline

```text
Untrusted PDF upload
  → validation + private storage
  → embedded text by page/block
  → OCR provider only when text is unusable
  → INVOICE / BILL_OF_LADING / UNKNOWN classification
  → document-type extractor
  → normalized field candidates + evidence
  → deterministic validation and canonical matching
  → correction / revalidation / approval
  → type-specific, idempotent canonical commit
```

`DocumentExtractor` is the plug-in protocol. `InvoiceExtractor` and `BillOfLadingExtractor` share it. OCR and storage are protocols with local/default adapters. Classification exposes only types the application truly supports. A future semantic extractor may propose candidates through the same protocol, but it cannot bypass confidence, validation, review, or commit rules.

Bill of Lading commitment builds one graph transactionally: source document → B/L → shipment → shipment-scoped container occurrences plus vessel/voyage and origin/destination ports. No intermediate commit is issued. Exceptions roll the session back so a partially created logistics graph cannot survive.

## Import lifecycle

An import follows controlled states:

```text
analyzed → mapped → validated ──→ committed
                        └──→ needs_review ──→ partially_committed ──→ committed
```

- **Analyzed:** source structure, raw rows, samples, and proposed mappings are stored.
- **Mapped:** a user has submitted choices. Confirmed non-null choices update company learning.
- **Validated:** all uncommitted rows have current deterministic validation results and no row needs review.
- **Needs review:** at least one uncommitted row is `review` or `invalid`.
- **Partially committed:** one or more rows are committed while unresolved or newly ready rows remain.
- **Committed:** every import row has been committed. This is terminal.

Rows transition among `pending`, `ready`, `review`, and `invalid` as mappings or value corrections are revalidated. `committed` is terminal. Mapping changes are allowed only before the first row is committed, because a column-wide reinterpretation after canonical persistence would require an explicit supersession model. Repeated commits skip already committed rows, and only `ready` rows are eligible.

## Mapping priority

The implemented order is:

1. company-confirmed mapping (`1.00` confidence)
2. configured known alias (`0.99`)
3. conservative string similarity when there is one strong, clearly separated candidate
4. unresolved / human review

Headers are normalized for case, whitespace, punctuation, and separators. The alias vocabulary is data-driven in `backend/app/input_engine/config/aliases.json`. Known ambiguous headers such as `REF`, `ID`, and `AMOUNT` are never guessed unless a user has previously confirmed a company-specific mapping.

The mapping service is the extension boundary for structural/value inference, semantic embeddings, or an LLM assistant. An external model is not required and would only propose mappings. It must never bypass normalization, validation, or the commit boundary.

## Auditability and provenance

`ImportJob` is the audit aggregate. It retains:

- original filename, source type, sheet names, selected sheet, and detected header row
- raw row values and source row numbers
- proposed/confirmed field mappings, confidence, and method
- system-normalized and effective corrected values plus final disposition
- structured validation issues and aggregate counts
- immutable correction records containing prior/effective values, field, unit, reason, time, and reviewer reference
- approval and commit timestamps plus the canonical shipment ID on each committed row
- the import job and source row on every imported shipment

Raw source JSON is never mutated by review. Corrections are overlays used to produce the effective normalized candidate. This supports practical lineage without an event-sourcing subsystem. Tabular source bytes remain intentionally unretained.

Document bytes are retained through `DocumentStorage`; local development writes below a controlled root with a tenant/document/checksum key. Only an opaque storage key is persisted, and no raw filesystem path is returned by an API. A private object-store adapter can replace local disk without changing review or commit services. Invoice lineage is `Invoice.source_document_id → SourceDocument → DocumentFieldCandidate → page/evidence → retained PDF`; effective reviewer values remain distinct from system-normalized values. B/L lineage uses `BillOfLading.source_document_id`, while document-created container occurrences retain `source_document_id` and their candidate group key.

## Review and query boundaries

History and row/document listings are paginated. Compact summaries are used for lists; complete evidence loads only for an open review. Mapping updates, value corrections, validation, approval, and commit rules live in application services rather than route handlers. Data Quality is calculated from tenant-scoped import, row, document, and candidate state.

## Tenant isolation and security

Every tenant-owned business and import record carries `company_id`. Repository operations require a company context and add it to reads and identity checks. Database constraints include the company where business uniqueness is tenant-relative.

Demo mode is intentionally narrow: it resolves one configured company server-side and rejects attempts to select another company through `X-Company-ID`. Production mode fails closed because user authentication, memberships, roles, and permissions are intentionally deferred. A production authentication adapter must derive allowed companies from the authenticated identity; a frontend-provided company ID alone is never authorization.

Other baseline controls include upload size/type/signature checks, filename sanitization, storage-path confinement, bounded PDF content streams, encrypted/corrupt/no-text handling, typed contracts, explicit validation, no embedded credentials, and CORS configuration. Documents are processed locally and are never transmitted to an external OCR/AI provider.

## Canonical data consumption

AI Analyst, automations, and FIN//TWIN should query the deterministic analytics service, canonical repositories, or future curated analytical projections. They must not independently reparse upload rows or reproduce KPI formulas.

- **Analytics:** implemented deterministic calculations over canonical shipments and finance records, with explicit currency, coverage, comparison, baseline, and provenance semantics.
- **AI Analyst:** query plan → controlled data tools → deterministic facts → language explanation.
- **Simulation:** versioned scenarios over validated historical distributions.
- **Documents:** new types implement classifier signals, an extractor protocol, normalization/validation rules, and a canonical commit adapter while reusing storage, evidence, correction, state, security, and review infrastructure.
- **Automations:** events should reference canonical IDs and retain triggering source lineage.

## Operational assumptions and risks

- One uploaded table represents shipment-oriented rows. Multi-table workbooks and one-to-many row expansion are future work.
- A row can create one shipment, one container, and one bill of lading in v0.1. The schema supports one-to-many relationships even though import expansion does not yet.
- Ports are matched by a UN/LOCODE-shaped value or normalized name. A reference port catalog should replace this heuristic.
- Document B/L ingestion validates ISO 6346 structure and check digit; the older spreadsheet import retains shape-only validation until its validator is unified.
- Currency validation checks a three-letter shape, not a maintained ISO 4217 table.
- Large uploads are processed synchronously. A background job boundary is needed before production-scale files.
- Mapping changes are locked after the first selective commit. Correcting already committed canonical data requires a future supersession workflow.
- Reviewer identity uses the current demo reviewer reference until production authentication supplies a verified user identity.
- Invoice extraction supports deterministic labeled fields and adjacent table label/value lines, not arbitrary visual layouts or line-item extraction.
- Scanned/image-only PDFs require a configured local OCR provider and otherwise fail explicitly with `OCR_REQUIRED`.
- VAT/accounting treatment is not inferred; extracted VAT facts remain evidence-backed candidates.
- Local document storage is for development. Production requires private encrypted storage, backup, retention, and malware/content scanning policy.
- Bill of Lading extraction targets clean, labeled digital documents and simple delimited container rows. Arbitrary carrier layouts and scanned documents still require a future layout/OCR adapter.
- Monetary analytics is single-currency because no governed FX-rate model exists. Contribution profit includes shipment-attributable cost only and is not net profit.
- Direct invoice-payment links are supported; split allocation of one payment across invoices is not modeled.
- Current analytical calculation is synchronous and in-process. Larger tenants will need measured query limits and potentially versioned projections/caching without changing metric definitions.

## Deployment

The runtime has no cloud-specific dependency. PostgreSQL and the two application processes can run in a public cloud, private cloud, Linux host, or Mac server. Object storage, queues, and identity providers remain adapters rather than domain dependencies.
