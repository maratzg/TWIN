const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    const detail = typeof body.detail === "object" ? body.detail?.message : body.detail;
    throw new Error(detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  context<T>() {
    return request<T>("/context");
  },
  upload<T>(file: File) {
    const data = new FormData();
    data.append("file", file);
    return request<T>("/imports", { method: "POST", body: data });
  },
  uploadDocument<T>(file: File) {
    const data = new FormData();
    data.append("file", file);
    return request<T>("/documents", { method: "POST", body: data });
  },
  documents<T>(search: string, status: string, page: number, documentType = "") {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    if (documentType) params.set("document_type", documentType);
    return request<T>(`/documents?${params.toString()}`);
  },
  document<T>(id: string) {
    return request<T>(`/documents/${id}`);
  },
  documentSource(id: string, inline = true) {
    return `${API_URL}/documents/${id}/source?inline=${inline}`;
  },
  classifyDocument<T>(id: string) {
    return request<T>(`/documents/${id}/classification`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_type: "INVOICE", reviewer_reference: "demo-reviewer" }),
    });
  },
  classifyDocumentAs<T>(id: string, documentType: "INVOICE" | "BILL_OF_LADING") {
    return request<T>(`/documents/${id}/classification`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_type: documentType, reviewer_reference: "demo-reviewer" }),
    });
  },
  correctDocumentField<T>(id: string, field: string, correctedValue: unknown) {
    return request<T>(`/documents/${id}/fields/${encodeURIComponent(field)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corrected_value: correctedValue, reviewer_reference: "demo-reviewer" }),
    });
  },
  correctDocumentCandidate<T>(id: string, candidateId: string, correctedValue: unknown) {
    return request<T>(`/documents/${id}/candidates/${candidateId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corrected_value: correctedValue, reviewer_reference: "demo-reviewer" }),
    });
  },
  revalidateDocument<T>(id: string) {
    return request<T>(`/documents/${id}/revalidate`, { method: "POST" });
  },
  approveDocument<T>(id: string) {
    return request<T>(`/documents/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer_reference: "demo-reviewer" }),
    });
  },
  commitDocument<T>(id: string) {
    return request<T>(`/documents/${id}/commit`, { method: "POST" });
  },
  invoices<T>(search: string, page: number) {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (search) params.set("search", search);
    return request<T>(`/invoices?${params.toString()}`);
  },
  billsOfLading<T>(search: string, page: number) {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (search) params.set("search", search);
    return request<T>(`/bills-of-lading?${params.toString()}`);
  },
  billOfLading<T>(id: string) {
    return request<T>(`/bills-of-lading/${id}`);
  },
  getMapping<T>(id: string) {
    return request<T>(`/imports/${id}/mapping`);
  },
  saveMapping<T>(id: string, mappings: unknown[], reprocess = false) {
    return request<T>(`/imports/${id}/mapping`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mappings, reprocess }),
    });
  },
  validate<T>(id: string) {
    return request<T>(`/imports/${id}/validate`, { method: "POST" });
  },
  commit<T>(id: string, rowIds?: string[]) {
    return request<T>(`/imports/${id}/commit`, {
      method: "POST",
      headers: rowIds ? { "Content-Type": "application/json" } : undefined,
      body: rowIds ? JSON.stringify({ row_ids: rowIds }) : undefined,
    });
  },
  history<T>(search: string, status: string, page: number) {
    const params = new URLSearchParams({ page: String(page), page_size: "10" });
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    return request<T>(`/imports?${params.toString()}`);
  },
  quality<T>() {
    return request<T>("/data-quality");
  },
  importDetail<T>(id: string) {
    return request<T>(`/imports/${id}`);
  },
  importRows<T>(id: string, disposition: string, page: number) {
    const params = new URLSearchParams({ page: String(page), page_size: "25" });
    if (disposition !== "all") params.set("disposition", disposition);
    return request<T>(`/imports/${id}/rows?${params.toString()}`);
  },
  rowDetail<T>(importId: string, rowId: string) {
    return request<T>(`/imports/${importId}/rows/${rowId}`);
  },
  correctRow<T>(importId: string, rowId: string, correction: unknown) {
    return request<T>(`/imports/${importId}/rows/${rowId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(correction),
    });
  },
  revalidateRow<T>(importId: string, rowId: string) {
    return request<T>(`/imports/${importId}/rows/${rowId}/revalidate`, { method: "POST" });
  },
  revalidateRows<T>(importId: string, rowIds: string[]) {
    return request<T>(`/imports/${importId}/revalidate-rows`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ row_ids: rowIds }),
    });
  },
  approveRows<T>(importId: string, rowIds: string[]) {
    return request<T>(`/imports/${importId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ row_ids: rowIds }),
    });
  },
  shipments<T>(search: string, page: number) {
    const params = new URLSearchParams({ page: String(page), page_size: "25" });
    if (search) params.set("search", search);
    return request<T>(`/shipments?${params.toString()}`);
  },
  shipment<T>(id: string) {
    return request<T>(`/shipments/${id}`);
  },
  analyticsMetrics<T>() {
    return request<T>("/analytics/metrics");
  },
  analyticsOptions<T>() {
    return request<T>("/analytics/options");
  },
  analyticsSummary<T>(params: URLSearchParams = new URLSearchParams()) {
    return request<T>(`/analytics/summary?${params.toString()}`);
  },
  analyticsTimeseries<T>(params: URLSearchParams) {
    return request<T>(`/analytics/timeseries?${params.toString()}`);
  },
  analyticsBreakdown<T>(params: URLSearchParams) {
    return request<T>(`/analytics/breakdown?${params.toString()}`);
  },
  analyticsInsights<T>(params: URLSearchParams = new URLSearchParams()) {
    return request<T>(`/analytics/insights?${params.toString()}`);
  },
  analyticsDrilldown<T>(params: URLSearchParams) {
    return request<T>(`/analytics/drilldown?${params.toString()}`);
  },
};
