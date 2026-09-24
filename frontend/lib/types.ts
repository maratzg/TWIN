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
