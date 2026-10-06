export type MappingItem = {
  source_column: string;
  canonical_field: string | null;
  confidence: number;
  mapping_method: string;
  user_confirmed: boolean;
  sample_values: string[];
};

export type ImportAnalysis = {
  id: string;
  filename: string;
  source_type: string;
  selected_sheet: string | null;
  sheet_names: string[];
  header_row: number;
  status: string;
  detected_row_count: number;
  ready_count: number;
  imported_count: number;
  review_count: number;
  rejected_count: number;
  created_at: string;
  committed_at: string | null;
  columns: MappingItem[];
};

export type MappingResponse = {
  import_id: string;
  canonical_fields: string[];
  mappings: MappingItem[];
};

export type ValidationIssue = {
  id?: string | null;
  row_id?: string | null;
  row: number | null;
  field: string | null;
  severity: "INFO" | "WARNING" | "ERROR";
  code: string;
  message: string;
};

export type ValidationSummary = {
  import_id: string;
  status: string;
  ready: number;
  needs_review: number;
  invalid: number;
  committed: number;
  issues: ValidationIssue[];
};

export type CommitSummary = {
  import_id: string;
  status: string;
  requested: number;
  committed: number;
  skipped: { row_id: string; row_number: number; reason: string }[];
  ready: number;
  invalid: number;
  total_committed: number;
  imported: number;
  needs_review: number;
  rejected: number;
};

export type ImportSummary = Omit<ImportAnalysis, "columns">;

export type ImportHistoryPage = {
  items: ImportSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type ImportDetail = ImportSummary & {
  company_name: string;
  mapping_complete: boolean;
  validation_complete: boolean;
  mappings: MappingItem[];
  canonical_fields: string[];
};

export type DataQualitySummary = {
  ready_rows: number;
  review_rows: number;
  invalid_rows: number;
  total_evaluated_rows: number;
  ready_percent: number;
  review_percent: number;
  invalid_percent: number;
  unresolved_issues: number;
  imports_requiring_review: number;
  recent_successful_imports: number;
  recent_failed_imports: number;
  documents_awaiting_review: number;
  failed_document_processing: number;
  unresolved_document_fields: number;
  recent_processed_documents: number;
};

export type DocumentRecord = {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
  status: string;
  document_type: string;
  classification_confidence: number;
  classification_method: string | null;
  classification_signals: string[];
  extraction_version: string | null;
  extraction_method: string | null;
  page_count: number;
  field_count: number;
  review_count: number;
  error_count: number;
  approved_at: string | null;
  approved_by: string | null;
  committed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentSummary = DocumentRecord & {
  ready_fields: number;
  review_fields: number;
  error_fields: number;
  canonical_invoice_id: string | null;
  canonical_invoice_number: string | null;
  canonical_bill_of_lading_id: string | null;
  canonical_bill_of_lading_number: string | null;
};

export type DocumentHistoryPage = {
  items: DocumentSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type DocumentPage = {
  id: string;
  page_number: number;
  text: string;
  blocks: Record<string, unknown>[];
  extraction_method: string;
  char_count: number;
};

export type DocumentFieldCandidate = {
  id: string;
  field_name: string;
  group_type: "document" | "container";
  group_index: number;
  raw_value: string | null;
  system_normalized_value: unknown;
  normalized_value: unknown;
  confidence: number;
  extraction_method: string;
  page_number: number | null;
  evidence: string | null;
  bounding_box: Record<string, number> | null;
  status: "ready" | "review" | "error";
  matched_entity_type: string | null;
  matched_entity_id: string | null;
  match_method: string | null;
  match_confidence: number | null;
};

export type DocumentIssue = {
  id: string;
  field: string | null;
  severity: "INFO" | "WARNING" | "ERROR";
  code: string;
  message: string;
};

export type DocumentCorrection = {
  id: string;
  field_name: string;
  previous_value: unknown;
  corrected_value: unknown;
  reason: string | null;
  reviewer_reference: string | null;
  created_at: string;
};

export type CanonicalInvoiceReference = {
  id: string;
  invoice_number: string;
  direction: string;
  status: string;
};

export type CanonicalBillOfLadingReference = {
  id: string;
  number: string;
  shipment_id: string;
  source_document_id: string | null;
};

export type DocumentDetail = {
  document: DocumentRecord;
  pages: DocumentPage[];
  candidates: DocumentFieldCandidate[];
  issues: DocumentIssue[];
  corrections: DocumentCorrection[];
  canonical_invoice: CanonicalInvoiceReference | null;
  canonical_bill_of_lading: CanonicalBillOfLadingReference | null;
  canonical_fields: string[];
};

export type Invoice = {
  id: string;
  source_document_id: string | null;
  invoice_number: string;
  direction: string;
  invoice_date: string;
  due_date: string | null;
  subtotal: string;
  vat: string;
  total: string;
  currency: string;
  status: string;
  customer_id: string | null;
  customer_name: string | null;
  supplier_id: string | null;
  supplier_name: string | null;
  shipment_id: string | null;
  created_at: string;
};

export type InvoiceHistoryPage = {
  items: Invoice[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type ImportRowListItem = {
  id: string;
  row_number: number;
  disposition: "pending" | "ready" | "review" | "invalid" | "committed";
  summary: {
    reference?: string | null;
    customer?: string | null;
    container?: string | null;
    gross_weight?: string | null;
  };
  issue_codes: string[];
  issue_count: number;
  correction_count: number;
  approved_at: string | null;
  committed_at: string | null;
};

export type ImportRowPage = {
  items: ImportRowListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type ImportCell = {
  source_column: string | null;
  raw_value: unknown;
  canonical_field: string | null;
  system_normalized_value: unknown;
  normalized_value: unknown;
  status: "valid" | "review" | "error" | "committed";
  issues: ValidationIssue[];
};

export type ImportCorrection = {
  id: string;
  correction_type: string;
  source_column: string | null;
  canonical_field: string | null;
  previous_value: unknown;
  corrected_value: unknown;
  unit: string | null;
  reason: string | null;
  reviewer_reference: string | null;
  created_at: string;
};

export type ImportRowDetail = {
  id: string;
  row_number: number;
  disposition: string;
  raw_data: Record<string, unknown>;
  system_normalized_data: Record<string, unknown> | null;
  normalized_data: Record<string, unknown> | null;
  approved_at: string | null;
  approved_by: string | null;
  committed_at: string | null;
  canonical_record_id: string | null;
  cells: ImportCell[];
  issues: ValidationIssue[];
  corrections: ImportCorrection[];
  canonical_fields: string[];
};

export type Shipment = {
  id: string;
  reference: string | null;
  booking_reference: string | null;
  customer: string | null;
  bill_of_lading: string | null;
  container: string | null;
  vessel: string | null;
  voyage: string | null;
  port_of_loading: string | null;
  port_of_discharge: string | null;
  etd: string | null;
  eta: string | null;
  gross_weight: string | null;
  teu: string | null;
  revenue: string | null;
  currency: string | null;
  status: string | null;
};

export type ShipmentPage = {
  items: Shipment[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type BillOfLadingContainer = {
  id: string;
  container_number: string;
  size_type: string | null;
  seal_number: string | null;
  package_count: number | null;
  package_type: string | null;
  gross_weight: string | null;
  teu: string | null;
  source_document_id: string | null;
  source_candidate_group: string | null;
};

export type BillOfLading = {
  id: string;
  number: string;
  source_document_id: string | null;
  shipment_id: string;
  shipment_reference: string | null;
  issue_date: string | null;
  carrier: string | null;
  shipper: string | null;
  shipper_supplier_id: string | null;
  consignee: string | null;
  consignee_customer_id: string | null;
  notify_party: string | null;
  vessel: string | null;
  voyage: string | null;
  port_of_loading: string | null;
  port_of_discharge: string | null;
  description_of_goods: string | null;
  total_packages: number | null;
  total_gross_weight: string | null;
  measurement: string | null;
  measurement_unit: string | null;
  containers: BillOfLadingContainer[];
  created_at: string;
};

export type BillOfLadingPage = {
  items: BillOfLading[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type ShipmentDetail = Shipment & {
  documents: { id: string; document_type: string; number: string; source_document_id: string | null }[];
  containers: {
    id: string;
    container_number: string;
    size_type: string | null;
    seal_number: string | null;
    package_count: number | null;
    package_type: string | null;
    gross_weight: string | null;
    teu: string | null;
    source_document_id: string | null;
  }[];
  invoices: {
    id: string;
    invoice_number: string;
    direction: string;
    total: string;
    currency: string;
    source_document_id: string | null;
  }[];
};

export type DecimalValue = string | number | null;

export type AnalyticsPeriod = {
  from_date: string;
  to_date: string;
};

export type MetricMetadata = {
  key: string;
  display_name: string;
  description: string;
  unit: string;
  calculation: string;
  supported_dimensions: string[];
  date_basis: string;
  aggregation: string;
  decimals: number;
};

export type AnalyticsCoverage = {
  label: string;
  covered_records: number;
  eligible_records: number;
  percent: DecimalValue;
  excluded_records: number;
  currency_exclusions: Record<string, number>;
  warnings: string[];
};

export type AnalyticsComparison = {
  current: DecimalValue;
  previous: DecimalValue;
  absolute_change: DecimalValue;
  percentage_change: DecimalValue;
  change_type: "absolute" | "percentage_points";
};

export type AnalyticsMetricValue = {
  metric: MetricMetadata;
  value: DecimalValue;
  currency: string | null;
  coverage: AnalyticsCoverage;
  comparison: AnalyticsComparison | null;
  components: Record<string, DecimalValue>;
};

export type AnalyticsSummary = {
  period: AnalyticsPeriod;
  comparison_period: AnalyticsPeriod;
  currency: string;
  filters: Record<string, string | null>;
  metrics: AnalyticsMetricValue[];
};

export type AnalyticsOption = { id: string; label: string };

export type AnalyticsOptions = {
  default_period: AnalyticsPeriod;
  default_currency: string;
  customers: AnalyticsOption[];
  routes: AnalyticsOption[];
  ports: AnalyticsOption[];
  vessels: AnalyticsOption[];
  voyages: AnalyticsOption[];
  currencies: AnalyticsOption[];
};

export type MetricRegistry = {
  metrics: MetricMetadata[];
  time_grains: string[];
  dimensions: string[];
};

export type TimeseriesPoint = {
  period: AnalyticsPeriod;
  label: string;
  values: Record<string, DecimalValue>;
  coverage: Record<string, AnalyticsCoverage>;
};

export type AnalyticsTimeseries = {
  period: AnalyticsPeriod;
  grain: string;
  currency: string;
  filters: Record<string, string | null>;
  metrics: MetricMetadata[];
  points: TimeseriesPoint[];
};

export type BreakdownRow = {
  dimension_id: string;
  dimension_label: string;
  values: Record<string, DecimalValue>;
  comparisons: Record<string, AnalyticsComparison | null>;
  coverage: Record<string, AnalyticsCoverage>;
  drilldown: { dimension: string; dimension_id: string };
};

export type AnalyticsBreakdown = {
  period: AnalyticsPeriod;
  comparison_period: AnalyticsPeriod;
  dimension: string;
  currency: string;
  filters: Record<string, string | null>;
  metrics: MetricMetadata[];
  rows: BreakdownRow[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type InsightContributor = {
  metric: string;
  current_value: DecimalValue;
  baseline_value: DecimalValue;
  absolute_change: DecimalValue;
  percentage_change: DecimalValue;
  change_type: string;
};

export type AnalyticsInsight = {
  id: string;
  type: string;
  severity: "info" | "warning" | "critical" | "positive";
  title: string;
  entity_type: string;
  entity_id: string | null;
  entity_label: string;
  metric: string;
  current_value: DecimalValue;
  baseline_value: DecimalValue;
  absolute_change: DecimalValue;
  percentage_change: DecimalValue;
  change_type: string;
  contributors: InsightContributor[];
  period: AnalyticsPeriod;
  baseline_period: AnalyticsPeriod;
  evidence: Record<string, unknown>;
  drilldown: Record<string, string>;
  rank_score: DecimalValue;
};

export type AnalyticsInsights = {
  period: AnalyticsPeriod;
  baseline_period: AnalyticsPeriod;
  baseline_window: string;
  currency: string;
  filters: Record<string, string | null>;
  insights: AnalyticsInsight[];
};

export type DrilldownItem = {
  record_type: "shipment" | "invoice";
  record_id: string;
  label: string;
  record_date: string;
  customer: string | null;
  route: string | null;
  revenue: DecimalValue;
  cost: DecimalValue;
  teu: DecimalValue;
  gross_weight: DecimalValue;
  invoice_total: DecimalValue;
  outstanding: DecimalValue;
  currency: string | null;
  shipment_id: string | null;
  invoice_id: string | null;
  cost_record_ids: string[];
  container_ids: string[];
  source_document_ids: string[];
  import_job_id: string | null;
  source_row_number: number | null;
};

export type AnalyticsDrilldown = {
  metric: MetricMetadata;
  period: AnalyticsPeriod;
  currency: string;
  filters: Record<string, string | null>;
  dimension: string | null;
  dimension_id: string | null;
  reconciled_value: DecimalValue;
  coverage: AnalyticsCoverage;
  items: DrilldownItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};
