export type RequestMode = "live" | "mock" | "retrieve_only";
export type ResponseMode = "live" | "mock" | "mock_fallback" | "retrieve_only";

export type Source = {
  rank: number;
  file_name: string;
  domain: string | null;
  topic: string | null;
  year: string | null;
  page: number | string | null;
  preview: string;
};

export type RetrievalMetadata = {
  use_hybrid: boolean;
  use_rerank: boolean;
  detected_year: string | null;
  final_k: number;
  initial_k: number;
};

export type ChatRequest = {
  question: string;
  mode: RequestMode;
  final_k: number;
};

export type ChatResponse = {
  answer: string;
  sources: Source[];
  retrieval: RetrievalMetadata;
  mode_used: ResponseMode;
  latency_ms: number;
  warning: string | null;
};

export type RetrieveResponse = {
  sources: Source[];
  retrieval: RetrievalMetadata;
  mode_used: "retrieve_only";
  latency_ms: number;
  warning: string | null;
};

export type HealthResponse = {
  status: "ok";
  app_name: string;
  vectorstore_available: boolean;
  chunks_available: boolean;
  live_llm_configured: boolean;
  groq_model_name: string | null;
  langsmith_tracing_enabled: boolean;
  langsmith_project: string | null;
};

export type RetrieverBackend = "faiss" | "postgres";

export type AdminMetric = {
  label: string;
  value: string;
  detail: string;
};

export type AdminSeriesPoint = {
  label: string;
  value: number;
};

export type AdminQuestionStat = {
  question: string;
  count: number;
  last_asked_at: string;
  avg_latency_ms: number;
};

export type AdminJobStat = {
  id: string;
  source_type: string;
  job_mode: string;
  status: "queued" | "running" | "succeeded" | "failed";
  summary: string;
  started_at: string | null;
  finished_at: string | null;
  source_documents: number;
  chunks: number;
  task_id: string | null;
};

export type IngestJobSummary = {
  id: string;
  task_id: string | null;
  source_type: string;
  job_mode: string;
  status: "queued" | "running" | "succeeded" | "failed";
  requested_paths: string[];
  uploaded_file_ids: string[];
  result_message: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type IngestJobDetail = IngestJobSummary & {
  started_at: string | null;
  finished_at: string | null;
};

export type AdminUploadStat = {
  id: string;
  filename: string;
  size_bytes: number;
  checksum: string;
  job_id: string | null;
  created_at: string;
};

export type UploadedFileSummary = {
  id: string;
  original_filename: string;
  stored_path: string;
  content_type: string | null;
  file_size_bytes: number;
  checksum: string;
  created_at: string;
  updated_at: string;
};

export type AdminHealthFlag = {
  label: string;
  value: string;
};

export type AdminCorpusStatus = {
  status: "healthy" | "needs_ingest" | "broken";
  active_documents: number;
  active_chunks: number;
  orphan_chunks: number;
  documents_without_chunks: number;
  documents_with_missing_files: number;
};

export type AdminDashboardResponse = {
  retriever_backend: RetrieverBackend;
  corpus: AdminCorpusStatus;
  metrics: AdminMetric[];
  search_volume: AdminSeriesPoint[];
  latency_series: AdminSeriesPoint[];
  ingest_series: AdminSeriesPoint[];
  top_questions_week: AdminQuestionStat[];
  top_questions_month: AdminQuestionStat[];
  recent_jobs: AdminJobStat[];
  recent_uploads: AdminUploadStat[];
  health_flags: AdminHealthFlag[];
  latest_query: string | null;
  latest_ingest_at: string | null;
  latest_failed_ingest_at: string | null;
};

export type AdminPaginatedResponse<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type AdminRetrieverBackendResponse = {
  retriever_backend: RetrieverBackend;
  override_enabled: boolean;
};

export type AdminUploadSortKey = "filename" | "size" | "checksum" | "job_id" | "created_at";
export type AdminJobSortKey =
  | "id"
  | "source_type"
  | "job_mode"
  | "status"
  | "started_at"
  | "finished_at"
  | "source_documents"
  | "chunks";
export type SortDirection = "asc" | "desc";
