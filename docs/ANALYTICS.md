# Deterministic Analytics Semantics

## Purpose and trust boundary

Milestone 4A derives operational and financial facts from committed canonical records. The chain is:

```text
Canonical database → metric registry → query/aggregation engine
  → comparison/baseline engine → structured insights → typed API → UI
```

The backend is authoritative. The browser formats and visualizes returned values; it does not recalculate KPIs. No LLM, prediction, exchange-rate inference, or persisted analytics truth participates in a calculation.

## Analytics-readiness audit

The existing schema is sufficient for the required calculations:

- `Shipment` contains tenant, customer, operational dates, route/voyage, shipment revenue, currency, gross weight, and import provenance.
- `Container` contains shipment-scoped occurrences, TEU, weight, status, and optional document provenance.
- `Cost` contains Decimal amount, currency, cost date, supplier, and an optional shipment attribution.
- `Invoice` contains receivable/payable direction, customer/supplier/shipment links, invoice/due dates, Decimal total, currency, status, and optional document provenance.
- `Payment` supports multiple payments per invoice with payment date, amount, and currency.
- canonical customers, ports, vessels, and voyages provide stable dimension identities.
- `ImportRow.canonical_record_id`, `Shipment.import_job_id/source_row_number`, and document source IDs retain the existing provenance paths.

Gaps deliberately not filled:

- there is no FX-rate model, so currencies are never converted or summed together;
- there is no general-ledger expense model, so only **contribution profit**, never net profit, is reported;
- payment allocation across several invoices is not modeled; payment analytics only uses directly linked payments;
- container status is not governed enough to fabricate loaded/empty state. Only explicit `loaded` and `empty` values are counted;
- general costs without `shipment_id` are not attributed to shipments or profitability.

Milestone 4A adds query-oriented composite indexes but no duplicated KPI columns or materialized analytics tables.

## Common query semantics

Every query is scoped by the authenticated company resolved on the server. The API never accepts a company ID as authorization.

The inclusive reporting period is `[from_date, to_date]`. When omitted, `to_date` is the latest canonical shipment ETD or invoice date available to the company, and `from_date` is 89 days earlier. Filters combine with AND semantics.

Supported dimensions are customer, route, port of loading (POL), port of discharge (POD), vessel, and voyage. Route identity is the canonical `(origin_port_id, destination_port_id)` pair and its display label is `POL name → POD name`. Missing identities use an explicit unresolved bucket; strings are never used as alternate route identities.

Supported grains are:

- day: calendar date;
- week: ISO week beginning Monday;
- month: calendar month;
- quarter: calendar quarter;
- year: calendar year.

## Currency behavior

No FX conversion exists. A monetary request therefore has exactly one selected currency, defaulting to `Company.default_currency`.

- Shipment revenue contributes only when `Shipment.currency` equals the selected currency.
- Attributable cost contributes only when `Cost.currency` equals the selected currency.
- Invoice/payment metrics contribute only when the invoice and linked payment currency equal the selected currency.
- Other currencies are excluded, never converted, and returned as explicit exclusion counts grouped by currency.
- Operational metrics such as shipment count, containers, TEU, and weight are not currency-filtered unless a future explicit operational currency filter is introduced.

This boundary is isolated so a future governed FX provider can convert facts before they reach the metric calculations.

## Metric definitions

All money uses `Decimal`/database `NUMERIC`. API decimal values are serialized without binary floating-point arithmetic. Percentages are returned in percentage points (`18.6` means 18.6%).

| Metric | Formula and source | Date basis | Missing/zero behavior | Aggregation |
| --- | --- | --- | --- | --- |
| Revenue | Sum of non-null `Shipment.revenue` in selected currency | Shipment ETD | Missing revenue and other currencies excluded and disclosed | Additive for one currency |
| Attributable cost | Sum of `Cost.amount` in selected currency where `Cost.shipment_id` resolves to an in-scope shipment | Shipment ETD | General/unmatched and other-currency costs excluded | Additive for one currency |
| Contribution profit | Revenue minus recorded attributable cost on the cohort of shipments that has both values in the selected currency | Shipment ETD | Shipments missing either side are excluded and disclosed rather than treated as zero-cost/zero-revenue | Additive for the same complete cohort and one currency |
| Contribution margin % | Complete-cohort contribution profit / complete-cohort revenue × 100 | Shipment ETD | Null when complete-cohort revenue is zero | Recalculate from additive components; never average row margins |
| Shipment count | Count of canonical shipments | Shipment ETD | Shipments without ETD are excluded and counted as a date-coverage gap | Additive across disjoint periods/dimensions |
| Container count | Count of shipment-scoped container occurrences | Shipment ETD | Zero when an in-scope shipment has no container | Additive |
| Loaded containers | Count where normalized status is exactly `loaded` | Shipment ETD | Unknown statuses excluded and disclosed | Additive |
| Empty containers | Count where normalized status is exactly `empty` | Shipment ETD | Unknown statuses excluded and disclosed | Additive |
| Loaded/empty ratio | Loaded containers / empty containers | Shipment ETD | Null when empty count is zero | Recalculate from counts |
| TEU | Sum of non-null `Container.teu` | Shipment ETD | Containers without valid TEU are excluded and disclosed | Additive |
| Gross weight | Sum of non-null `Shipment.gross_weight` in kilograms | Shipment ETD | Missing shipment weight excluded and disclosed | Additive |
| Revenue/shipment | Revenue / shipments carrying selected-currency revenue | Shipment ETD | Null for zero denominator | Recalculate from components |
| Cost/shipment | Cost / shipments carrying selected-currency attributable cost | Shipment ETD | Null for zero denominator | Recalculate from components |
| Profit/shipment | Contribution profit / financially complete shipment count | Shipment ETD | Null for zero denominator; finance coverage accompanies value | Recalculate from components |
| Revenue/TEU | Revenue / valid TEU on revenue-bearing shipments | Shipment ETD | Null for zero TEU | Recalculate from components |
| Cost/TEU | Cost / valid TEU on cost-bearing shipments | Shipment ETD | Null for zero TEU | Recalculate from components |
| Profit/TEU | Contribution profit / valid TEU on shipments with selected-currency finance facts | Shipment ETD | Null for zero TEU | Recalculate from components |
| Invoice value | Sum of receivable invoice totals in selected currency | Invoice date | Missing/unselected currencies excluded | Additive for one currency |
| Average invoice value | Receivable invoice value / receivable invoice count | Invoice date | Null for zero invoices | Recalculate from components |
| Outstanding receivables | For receivable invoices issued on/before period end: max(invoice total − linked payments posted on/before period end, 0) | Stock as of `to_date` | Unlinked/mismatched-currency payments do not reduce balance and are disclosed | Additive for one currency/as-of date |
| Outstanding payables | Same balance calculation for payable invoices | Stock as of `to_date` | Same safeguards as receivables | Additive for one currency/as-of date |
| Average payment delay | Average calendar days from due date to final payment date for fully paid receivable invoices | Invoice date; payments through `to_date` | Invoices without due date or complete direct payment coverage excluded | Not additive; recalculate from invoice observations |
| Customer concentration | Largest customer's selected-currency revenue / total selected-currency revenue × 100 | Shipment ETD | Null for zero revenue; unassigned customer is disclosed separately and is not treated as a named customer | Recalculate from customer totals |
| Route concentration | Largest canonical route's TEU / total TEU × 100 | Shipment ETD | Null for zero TEU; unresolved route disclosed separately | Recalculate from route totals |

`Contribution profit` is not net profit. It includes recorded shipment-attributable costs only and omits overhead, tax, depreciation, financing, and unallocated expenses. Its complete-cohort restriction keeps missing costs from being silently interpreted as zero; the standalone revenue and cost KPIs still report all recorded values in their respective covered populations.

## Coverage

Every metric returns a reusable coverage object:

- `covered_records` and `eligible_records`;
- percentage when an eligible denominator exists;
- a metric-specific label;
- excluded record count;
- currency exclusions where relevant;
- warnings when interpretation is materially incomplete.

Examples include shipments with recorded revenue, shipments with attributable cost, shipments with both financial sides, containers with valid TEU, shipments with weight, invoices with due dates, and fully paid invoices with directly linked payments. Coverage does not change a value silently; it explains the population behind it.

## Comparisons

The previous equivalent period has the same inclusive day count and ends one day before the current period begins.

- additive and ratio metrics return current value, previous value, and absolute change;
- non-percentage metrics return percentage change only when the previous value is non-zero;
- percentage metrics return percentage-point change and do not label it as percent growth;
- unavailable or zero-baseline comparisons return null rather than infinity or a fabricated percentage.

## Baselines

Insight baselines end before the current period starts and never overlap it. Supported baseline windows are trailing 4 weeks, trailing 8 weeks, and trailing 3 calendar months. The default is trailing 3 months. A baseline returns its explicit dates and observation/sample counts.

## Insight engine

Insights are structured deterministic records. Thresholds are centralized in application settings and can later become company-specific. Demo defaults are:

- margin drop: 3.0 percentage points;
- cost increase: 10%;
- revenue change: 10%;
- volume change: 25%;
- customer concentration: 30%;
- route concentration: 35%;
- payment delay deterioration: 7 days;
- expensive shipment: robust z-score of at least 3.0 with at least 8 comparable route observations;
- minimum route/customer sample: 8 shipments, 5 paid invoices for payment-delay rules, or 5 outstanding invoices for receivable-risk rules.

Implemented rules:

- route margin deterioration with revenue/TEU, cost/TEU, and volume contributors;
- cost/TEU increase, grouped into the related margin insight when both fire;
- company revenue increase/decrease;
- TEU volume change with sample-size suppression;
- customer and route concentration;
- customer payment-delay deterioration;
- outstanding receivable concentration/aging risk;
- expensive shipment anomalies using route median and median absolute deviation (MAD);
- company revenue growth with margin decline;
- materially improving customer contribution margin.

The engine uses `contributors`, never causal claims. Rules suppress tiny samples, rank by severity/magnitude/financial impact/coverage, deduplicate related movements, and return a bounded list. No opaque confidence score is invented.

## Drill-down and provenance

Drill-down returns stable canonical IDs and the additive components used by a metric. Shipment rows include customer, route, date, revenue, recorded cost, TEU, weight, currency, import job/source row, and related document IDs where available. Invoice rows include invoice/payment components and source document ID.

The intended path remains:

```text
KPI or insight → calculation metadata → canonical record
  → import row or source document → retained evidence/original source
```

Pagination is applied to drill-down records. Totals are calculated before pagination so displayed reconciliation is independent of the current page.

## API shape

- `GET /api/v1/analytics/metrics` — registry metadata.
- `GET /api/v1/analytics/options` — tenant-scoped filter/dimension options and default date range.
- `GET /api/v1/analytics/summary` — management KPIs with comparisons and coverage.
- `GET /api/v1/analytics/timeseries` — server-side time aggregation.
- `GET /api/v1/analytics/breakdown` — dimension aggregation, sorting, and pagination.
- `GET /api/v1/analytics/insights` — ranked structured insights and baseline metadata.
- `GET /api/v1/analytics/drilldown` — reconciled canonical contributors and provenance references.

Responses are typed and include metric metadata, period, selected currency, filters, comparison/baseline, coverage, and values. No endpoint accepts arbitrary SQL.

## Known limitations

- no FX conversion or consolidated multi-currency money KPI;
- no accrual/revenue-recognition schedule beyond shipment revenue on ETD;
- no overhead/general-ledger profitability and therefore no net profit;
- no payment allocation across invoices or bank reconciliation;
- no materialized warehouse, cache, forecasting, recommendations, or AI explanations;
- shipment records without ETD are intentionally absent from period flow metrics;
- analytics reflects committed canonical state and does not interpret uncommitted review candidates.
