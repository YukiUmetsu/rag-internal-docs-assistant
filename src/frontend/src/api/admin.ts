import { requestFormData, requestJson } from "./request";
import type {
  AdminDashboardResponse,
  AdminJobSortKey,
  AdminJobStat,
  AdminPaginatedResponse,
  AdminRetrieverBackendResponse,
  AdminUploadSortKey,
  AdminUploadStat,
  RetrieverBackend,
  SortDirection,
  IngestJobDetail,
  UploadedFileSummary,
} from "./types";

type AdminJobsQuery = {
  limit?: number;
  offset?: number;
  sortBy?: AdminJobSortKey;
  sortDir?: SortDirection;
  days?: number;
};

type AdminUploadsQuery = {
  limit?: number;
  offset?: number;
  sortBy?: AdminUploadSortKey;
  sortDir?: SortDirection;
};

function buildQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) {
      continue;
    }
    searchParams.set(key, String(value));
  }
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export function getAdminDashboard(): Promise<AdminDashboardResponse> {
  return requestJson<AdminDashboardResponse>("/api/admin/dashboard");
}

export function getAdminRetrieverBackend(): Promise<AdminRetrieverBackendResponse> {
  return requestJson<AdminRetrieverBackendResponse>("/api/admin/retriever-backend");
}

export function setAdminRetrieverBackend(
  retrieverBackend: RetrieverBackend
): Promise<AdminRetrieverBackendResponse> {
  return requestJson<AdminRetrieverBackendResponse>("/api/admin/retriever-backend", {
    method: "POST",
    body: JSON.stringify({ retriever_backend: retrieverBackend }),
  });
}

export function listAdminUploads(
  query: AdminUploadsQuery
): Promise<AdminPaginatedResponse<AdminUploadStat>> {
  const queryString = buildQueryString({
    limit: query.limit,
    offset: query.offset,
    sort_by: query.sortBy,
    sort_dir: query.sortDir,
  });
  return requestJson<AdminPaginatedResponse<AdminUploadStat>>(`/api/admin/uploads${queryString}`);
}

export function uploadAdminFiles(files: File[]): Promise<UploadedFileSummary[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return requestFormData<UploadedFileSummary[]>("/api/ingest/uploads", formData, {
    method: "POST",
  });
}

export function listAdminJobs(query: AdminJobsQuery): Promise<AdminPaginatedResponse<AdminJobStat>> {
  const queryString = buildQueryString({
    limit: query.limit,
    offset: query.offset,
    sort_by: query.sortBy,
    sort_dir: query.sortDir,
    days: query.days,
  });
  return requestJson<AdminPaginatedResponse<AdminJobStat>>(`/api/admin/jobs${queryString}`);
}

export function getAdminJobDetail(jobId: string): Promise<IngestJobDetail> {
  return requestJson<IngestJobDetail>(`/api/admin/jobs/${jobId}`);
}
