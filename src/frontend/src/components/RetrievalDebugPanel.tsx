import type { ChatResponse, RetrieveResponse } from "../api/types";
import { SourceCard } from "./SourceCard";

type Props = {
  response: ChatResponse | RetrieveResponse | null;
};

export function RetrievalDebugPanel({ response }: Props) {
  return (
    <aside className="debug-panel">
      <div className="panel-header">
        <span>Sources</span>
        {response ? <small>{response.latency_ms} ms</small> : null}
      </div>

      {response ? (
        <div className="debug-chips" aria-label="Retrieval details">
          <span>hybrid {response.retrieval.use_hybrid ? "on" : "off"}</span>
          <span>rerank {response.retrieval.use_rerank ? "on" : "off"}</span>
          <span>year {response.retrieval.detected_year ?? "none"}</span>
        </div>
      ) : null}

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
