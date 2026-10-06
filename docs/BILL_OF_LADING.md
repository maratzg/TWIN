# Bill of Lading Intelligence

## Scope

Milestone 3B processes digitally generated Bills of Lading through the existing Document Engine. It does not introduce a second storage, parsing, review, correction, or lifecycle system.

```text
PDF → parse/classify → BillOfLadingExtractor → candidates/groups
    → normalize/match/validate → review/correct → approve
    → transactional canonical logistics graph
```

## Extraction schema

Document-level candidates cover:

- B/L number and issue date;
- shipper, consignee, notify party, and carrier text;
- optional party identifiers;
- vessel name/IMO, voyage number, POL, POD, receipt, and delivery locations;
- shipment and booking references;
- goods description, total packages, gross weight, and measurement.

Containers are repeating candidate groups. Each group may contain number, size/type, seal, package count/type, and gross weight. Every field independently retains raw and normalized values, confidence, extraction method, page, evidence, correction history, and match state.

## Normalization and ISO 6346

Container numbers remove safe whitespace/punctuation and uppercase without changing digits. ISO 6346 validation distinguishes structural failure from check-digit failure. It applies the standard letter values and powers-of-two calculation locally; a bad check digit is reported and never repaired automatically.

Common unambiguous equipment types normalize to `20GP`, `40GP`, `40HC`, or `45HC`. Bare sizes such as `40` remain bare and do not receive a fabricated type. TEU derives only from unambiguous normalized types: 20-foot is 1 TEU; supported 40/45-foot types are 2 TEU.

Weights normalize to Decimal-compatible kilograms while retaining raw value and source unit. European and US thousands conventions are supported for common B/L expressions. Aggregate weight is compared with the sum of all available container weights using the configured tolerance.

## Matching order

- Ports: exact UN/LOCODE, unique exact normalized name, otherwise a reviewed creation candidate.
- Vessels: exact IMO, unique exact normalized name, otherwise a reviewed creation candidate.
- Voyages: vessel plus voyage number. Voyage number alone is never treated as globally unique.
- Parties: exact identifier/name and the existing conservative party matcher. Unresolved party text is retained and is not automatically duplicated.
- Shipments: exact shipment/booking/B/L reference first. Container identity is considered only with a complete matching vessel/voyage and route because container numbers are reusable. A unique exact vessel/voyage/POL/POD combination is a final conservative signal.

The minimum new-shipment candidate is a reviewed B/L number, vessel, voyage, POL, POD, and at least one valid container. Missing optional maritime fields do not become artificial errors.

## Conflicts and commit

A matched shipment's trusted voyage, ports, weights, and existing container occurrence data are never silently overwritten. Disagreement produces `CANONICAL_CONFLICT`, which blocks approval. Duplicate B/L identity is also blocking.

After explicit approval, one database transaction:

1. rechecks duplicate identity and conflicts;
2. links or creates ports, vessel, and vessel-specific voyage;
3. links an exact shipment or creates one from the reviewed minimum data;
4. creates the B/L and links exact party matches;
5. creates or reuses shipment-scoped container occurrences;
6. records document commitment and source provenance.

Any exception rolls back the entire graph. Repeating commit for the same source returns the existing B/L through its unique source-document relationship.

## Container occurrence semantics

`Container` remains shipment-scoped. It represents the occurrence of a physical container on that shipment, not a global equipment master. The same number may therefore occur on later shipments. The unique constraint is company + shipment + container number. This avoids falsely blocking normal equipment reuse while still preventing duplicate rows inside one shipment.

## Provenance

```text
BillOfLading.source_document_id
  → SourceDocument
  → DocumentFieldCandidate / container:n group
  → page + evidence
  → retained PDF

Container.source_document_id + source_candidate_group
  → originating container candidate group
```

Canonical B/L and shipment views link back to the review workbench and retained source PDF.

## Limitations

- Clean, labeled digital PDFs are supported; arbitrary carrier layouts are not universal.
- Container rows require recognizable table/delimited extracted text order.
- Scans remain `OCR_REQUIRED` without a configured local OCR provider.
- Port alias coverage is intentionally conservative pending governed master/reference data.
- There is no global physical-container master, carrier master, external AI extraction, or post-commit supersession workflow.
