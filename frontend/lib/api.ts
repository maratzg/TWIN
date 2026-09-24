const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  upload<T>(file: File) {
    const data = new FormData();
    data.append("file", file);
    return request<T>("/imports", { method: "POST", body: data });
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
};
