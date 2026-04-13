import type { HealthResponse, RequestMode } from "../api/types";

type Props = {
  health: HealthResponse | null;
  mode: RequestMode;
};

export function StatusBar({ health, mode }: Props) {
  return (
    <section className="status-bar">
      <img
        src="https://images.unsplash.com/photo-1450101499163-c8848c66ca85?auto=format&fit=crop&w=900&q=80"
        alt="Documents and analytics workspace"
      />
      <div>
        <span>System</span>
        <strong>{health?.status === "ok" ? "Ready" : "Checking"}</strong>
      </div>
      <div>
        <span>Mode</span>
        <strong>{mode.replace("_", " ")}</strong>
      </div>
      <div>
        <span>Artifacts</span>
        <strong>{health?.vectorstore_available && health?.chunks_available ? "available" : "pending"}</strong>
      </div>
      <div>
        <span>Live LLM</span>
        <strong>{health?.live_llm_configured ? health.groq_model_name ?? "configured" : "mock safe"}</strong>
      </div>
    </section>
  );
}
