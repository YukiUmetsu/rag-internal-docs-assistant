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
