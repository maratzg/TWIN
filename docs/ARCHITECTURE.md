# Architecture

## Scope and design

TWIN remains a modular monolith in Milestone 2. The review layer extends the established import service and repository boundaries without introducing queues, event sourcing, or a second persistence model.

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
  ├── import review and correction orchestration
  ├── tenant-scoped repositories
  └── canonical domain models
       │
       ▼
PostgreSQL (SQLite for isolated tests/smoke runs)
```

Routes translate HTTP to typed inputs and outputs. Services own workflow and transaction decisions. Repositories centralize tenant predicates. The input engine has no HTTP dependency and can later be called by scheduled jobs, document ingestion, or automation workers.

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

Raw source JSON is never mutated by review. Corrections are overlays used to produce the effective normalized candidate. This supports practical lineage without an event-sourcing subsystem. Original file bytes are not retained; deployments requiring evidentiary retention should add encrypted object storage plus checksums and retention policy.

## Review and query boundaries

History and row listings are paginated. Row list queries return compact summaries and batched issue/correction counts; the complete raw/system/effective cell view is loaded only for the open row. Mapping updates, value corrections, validation, approval, and commit rules live in application services rather than route handlers. Data Quality is calculated from tenant-scoped import and row state.

## Tenant isolation and security

Every tenant-owned business and import record carries `company_id`. Repository operations require a company context and add it to reads and identity checks. Database constraints include the company where business uniqueness is tenant-relative.

Demo mode is intentionally narrow: it resolves one configured company server-side and rejects attempts to select another company through `X-Company-ID`. Production mode fails closed because user authentication, memberships, roles, and permissions are intentionally deferred. A production authentication adapter must derive allowed companies from the authenticated identity; a frontend-provided company ID alone is never authorization.

Other baseline controls include upload size/type checks, sanitized stored filenames, typed contracts, explicit validation, no embedded credentials, and CORS configuration.

## Canonical data consumption

Future analytics, AI Analyst, automations, and FIN//TWIN should query canonical repositories or curated analytical projections. They must not independently reparse upload rows.

- **Analytics:** deterministic calculations over canonical shipments and finance records.
- **AI Analyst:** query plan → controlled data tools → deterministic facts → language explanation.
- **Simulation:** versioned scenarios over validated historical distributions.
- **Documents:** classify/OCR/extract → the same mapping, normalization, validation, and commit boundaries.
- **Automations:** events should reference canonical IDs and retain triggering source lineage.

## Operational assumptions and risks

- One uploaded table represents shipment-oriented rows. Multi-table workbooks and one-to-many row expansion are future work.
- A row can create one shipment, one container, and one bill of lading in v0.1. The schema supports one-to-many relationships even though import expansion does not yet.
- Ports are matched by a UN/LOCODE-shaped value or normalized name. A reference port catalog should replace this heuristic.
- Container validation checks shape, not the ISO 6346 check digit.
- Currency validation checks a three-letter shape, not a maintained ISO 4217 table.
- Large uploads are processed synchronously. A background job boundary is needed before production-scale files.
- Mapping changes are locked after the first selective commit. Correcting already committed canonical data requires a future supersession workflow.
- Reviewer identity uses the current demo reviewer reference until production authentication supplies a verified user identity.

## Deployment

The runtime has no cloud-specific dependency. PostgreSQL and the two application processes can run in a public cloud, private cloud, Linux host, or Mac server. Object storage, queues, and identity providers remain adapters rather than domain dependencies.
