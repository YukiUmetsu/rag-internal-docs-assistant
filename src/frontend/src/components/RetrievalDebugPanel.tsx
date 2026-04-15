import type { ChatResponse, RetrieveResponse } from "../api/types";
import { SourceCard } from "./SourceCard";

type Props = {
  response: ChatResponse | RetrieveResponse | null;
};

function formatLatency(milliseconds: number): string {
  return `${(milliseconds / 1000).toFixed(1)} s`;
}

export function RetrievalDebugPanel({ response }: Props) {
  const sourceCount = response?.sources.length ?? 0;

  return (
    <details className="debug-panel">
      <summary>
        <span>Sources</span>
        <small>
          {response ? `${sourceCount} sources · ${formatLatency(response.latency_ms)}` : "Run a search"}
        </small>
      </summary>

      <div className="sources-body">
        {response ? (
          <div className="debug-chips" aria-label="Retrieval details">
            <span>hybrid {response.retrieval.use_hybrid ? "on" : "off"}</span>
            <span>rerank {response.retrieval.use_rerank ? "on" : "off"}</span>
            <span>year {response.retrieval.detected_year ?? "none"}</span>
          </div>
        ) : null}

        <div className="source-list">
          {response?.sources.length ? (
            response.sources.map((source) => (
              <SourceCard key={`${source.rank}-${source.file_name}`} source={source} />
            ))
          ) : (
            <p className="empty-sources">Retrieved sources will appear here.</p>
          )}
        </div>
      </div>
    </details>
  );
}
