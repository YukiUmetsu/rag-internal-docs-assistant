import type { ChatResponse } from "../api/types";

type Props = {
  response: ChatResponse | null;
  isLoading: boolean;
  error: string | null;
};

export function AnswerPanel({ response, isLoading, error }: Props) {
  return (
    <section className="answer-panel">
      <div className="panel-header">
        <span>Answer</span>
        {response ? <small>{response.mode_used.replace("_", " ")}</small> : null}
      </div>

      {isLoading ? (
        <div className="loading-stack">
          <span>Retrieving sources</span>
          <span>Ranking candidates</span>
          <span>Preparing answer</span>
        </div>
      ) : null}

      {error ? <p className="error-message">{error}</p> : null}

      {!isLoading && !error && response ? (
        <>
          {response.warning ? <p className="warning-message">{response.warning}</p> : null}
          <p className="answer-text">{response.answer}</p>
        </>
      ) : null}

      {!isLoading && !error && !response ? (
        <p className="empty-answer">
          Ask about policies, incidents, support playbooks, or engineering docs.
        </p>
      ) : null}
    </section>
  );
}
