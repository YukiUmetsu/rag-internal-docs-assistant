import type { FormEvent } from "react";
import type { RequestMode } from "../api/types";

type Props = {
  question: string;
  mode: RequestMode;
  isLoading: boolean;
  onQuestionChange: (value: string) => void;
  onModeChange: (value: RequestMode) => void;
  onSubmit: () => void;
};

export function ChatComposer({
  question,
  mode,
  isLoading,
  onQuestionChange,
  onModeChange,
  onSubmit
}: Props) {
  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <div className="composer-top">
        <label htmlFor="question">Ask the internal assistant</label>
        <select
          value={mode}
          onChange={(event) => onModeChange(event.target.value as RequestMode)}
          aria-label="Answer mode"
        >
          <option value="live">Live answer</option>
          <option value="mock">Mock safe mode</option>
          <option value="retrieve_only">Retrieve only</option>
        </select>
      </div>
      <textarea
        id="question"
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder="Try: What was the refund window in 2025?"
        rows={4}
      />
      <button type="submit" disabled={isLoading || !question.trim()}>
        {isLoading ? "Working..." : "Ask assistant"}
      </button>
    </form>
  );
}
