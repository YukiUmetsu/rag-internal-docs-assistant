import type { AgentChatResponse, AssistantResponse } from "../api/types";
import { SourceCard } from "./SourceCard";

type Props = {
  response: AssistantResponse | null;
};

function formatLatency(milliseconds: number): string {
  return `${(milliseconds / 1000).toFixed(1)} s`;
}

function isAgentResponse(response: AssistantResponse): response is AgentChatResponse {
  return "tool_calls" in response;
}

export function RetrievalDebugPanel({ response }: Props) {
  const sourceCount = response?.sources.length ?? 0;
  const agentResponse = response && isAgentResponse(response) ? response : null;
  const retrievalResponse = response && !isAgentResponse(response) ? response : null;

  return (
    <details className="debug-panel">
      <summary>
        <span>{agentResponse ? "Agent trace" : "Sources"}</span>
        <small>
          {response
            ? agentResponse
              ? `${sourceCount} sources · ${agentResponse.tool_calls.length} tools`
              : `${sourceCount} sources · ${formatLatency(retrievalResponse?.latency_ms ?? 0)}`
            : "Run a search"}
        </small>
      </summary>

      <div className="sources-body">
        {response && "retrieval" in response ? (
          <div className="debug-chips" aria-label="Retrieval details">
            <span>hybrid {response.retrieval.use_hybrid ? "on" : "off"}</span>
            <span>rerank {response.retrieval.use_rerank ? "on" : "off"}</span>
            <span>year {response.retrieval.detected_year ?? "none"}</span>
          </div>
        ) : null}

        {response && "tool_calls" in response ? (
          <div className="debug-chips" aria-label="Agent details">
            <span>route {response.route ?? "none"}</span>
            <span>last tool {response.last_tool ?? "none"}</span>
          </div>
        ) : null}

        {response && "tool_calls" in response && response.tool_calls.length ? (
          <div className="tool-call-list">
            {response.tool_calls.map((toolCall, index) => (
              <div className="tool-call" key={`${toolCall.name}-${index}`}>
                <div className="source-card-top">
                  <strong>{toolCall.name}</strong>
                  <small>#{index + 1}</small>
                </div>
                {toolCall.output_preview ? <p>{toolCall.output_preview}</p> : null}
              </div>
            ))}
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
