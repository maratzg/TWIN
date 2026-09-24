# Import Review Workflow

## Purpose

The review workbench is an exception queue around the existing deterministic input engine. High-confidence rows can proceed without manual editing; uncertain or invalid rows remain fail-closed until their interpreted data is corrected and revalidated.

## States

Import states are `analyzed`, `mapped`, `validated`, `needs_review`, `partially_committed`, `committed`, and `failed`.

- `analyzed` means the file structure and initial mapping proposals are stored.
- `mapped` means mapping choices have been submitted but validation is not current.
- `validated` means every uncommitted row is currently ready.
- `needs_review` means at least one row is `review` or `invalid`.
- `partially_committed` means at least one row is committed and other rows remain.
- `committed` means every row is committed and the import is terminal.
- `failed` is recoverable through a new mapping submission.

Row states are `pending`, `ready`, `review`, `invalid`, and `committed`. Validation can move an uncommitted row between ready, review, and invalid. A committed row is immutable in this workflow.

## Value corrections

A row correction never changes `raw_data`. The service normalizes the reviewer-entered value for the selected canonical field, records an `ImportCorrection`, overlays the correction onto the system interpretation, and deterministically revalidates the import. Gross weight corrections explicitly accept `kg` or `tonnes`; tonnes are converted to kilograms before validation.

The row detail API exposes source column, raw value, mapped field, system-normalized value, effective normalized value, status, and issues. The correction trail exposes previous and corrected values, reason, unit, reviewer reference, and timestamp.

## Mapping corrections and learning

A confirmed column mapping applies to all uncommitted rows in the import. With reprocessing enabled, it immediately re-normalizes and revalidates those rows and refreshes counts. A mapping correction is audited and saved as a company-specific `LearnedMapping`; this company-confirmed mapping has priority on later imports.

Mappings become locked after any row is committed. This prevents a column-wide reinterpretation from silently disagreeing with canonical data already created.

## Approval, revalidation, and commit

Reviewers can revalidate one row, selected rows, or the import. Duplicate checks require import-wide context, so selected-row revalidation still evaluates the complete uncommitted import while returning consistent aggregate results.

Approval records reviewer/time only for currently ready rows. Approval does not bypass validation and does not create canonical data.

Commit accepts selected row IDs or all ready rows. At the transaction boundary it rechecks eligibility and canonical duplicate identity. Ready rows create canonical shipments and receive commit timestamps and canonical IDs. Invalid, review, and already committed rows are skipped with explicit reasons. Repeating the same request cannot create a second shipment from an already committed import row.

## API surface

- `GET /api/v1/imports` — paginated history with filename and status filters
- `GET /api/v1/imports/{id}` — import metadata and current counts
- `GET /api/v1/imports/{id}/rows` — paginated rows by disposition/search
- `GET /api/v1/imports/{id}/rows/{row_id}` — complete row/cell/audit detail
- `PATCH /api/v1/imports/{id}/rows/{row_id}` — save a value correction and revalidate
- `PUT /api/v1/imports/{id}/mapping` — confirm mappings, optionally reprocess
- `POST /api/v1/imports/{id}/rows/{row_id}/revalidate` — revalidate from retained source
- `POST /api/v1/imports/{id}/revalidate` — revalidate the import
- `POST /api/v1/imports/{id}/approve` — approve selected ready rows
- `POST /api/v1/imports/{id}/commit` — commit selected or all ready rows
- `GET /api/v1/imports/{id}/issues` — structured current issues
- `GET /api/v1/data-quality` — tenant-scoped ingestion-quality summary

## Isolation and limitations

Every operation resolves the import through the authenticated company context and scopes row, issue, correction, mapping, and commit access through that parent. Demo mode permits only the configured demo company. Production mode continues to fail closed until a real identity/membership adapter is supplied.

Processing remains synchronous and original upload bytes are not retained. Post-commit correction/supersession, production user identities, background processing, and object-storage retention are intentionally deferred.
