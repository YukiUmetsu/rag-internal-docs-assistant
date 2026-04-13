import type { ChatResponse, RetrieveResponse } from "../api/types";
import { SourceCard } from "./SourceCard";

type Props = {
  response: ChatResponse | RetrieveResponse | null;
};

export function RetrievalDebugPanel({ response }: Props) {
  return (
    <aside className="debug-panel">
      <div className="panel-header">
        <span>Retrieval</span>
        {response ? <small>{response.latency_ms} ms</small> : null}
      </div>

      <div className="debug-grid">
        <div>
          <span>Hybrid</span>
          <strong>{response?.retrieval.use_hybrid ? "on" : "off"}</strong>
        </div>
        <div>
          <span>Rerank</span>
          <strong>{response?.retrieval.use_rerank ? "on" : "off"}</strong>
        </div>
        <div>
          <span>Year filter</span>
          <strong>{response?.retrieval.detected_year ?? "none"}</strong>
        </div>
        <div>
          <span>Initial k</span>
          <strong>{response?.retrieval.initial_k ?? 12}</strong>
        </div>
      </div>

      <div className="source-list">
        {response?.sources.length ? (
          response.sources.map((source) => <SourceCard key={`${source.rank}-${source.file_name}`} source={source} />)
        ) : (
          <p className="empty-sources">Retrieved source cards will appear here.</p>
        )}
      </div>
    </aside>
  );
}
