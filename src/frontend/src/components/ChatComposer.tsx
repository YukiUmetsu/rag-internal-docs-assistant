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
      <input
        id="question"
        type="text"
        value={question}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder="What was the refund window in 2025?"
      />
      <select
        value={mode}
        onChange={(event) => onModeChange(event.target.value as RequestMode)}
        aria-label="Answer mode"
      >
        <option value="live">Live answer</option>
        <option value="mock">Mock safe mode</option>
        <option value="retrieve_only">Retrieve only</option>
      </select>
      <button
        className={isLoading ? "is-loading" : undefined}
        type="submit"
        disabled={isLoading || !question.trim()}
      >
        {isLoading ? "Searching..." : "Ask"}
      </button>
    </form>
  );
}
