import { useEffect, useMemo, useState, type FormEvent } from "react";

import { submitFeedback } from "../api/feedback";
import type { FeedbackReasonCode, FeedbackVerdict } from "../api/types";

type Props = {
  requestId: string | null | undefined;
  onSuccess?: () => void;
};

type FeedbackOption = {
  value: FeedbackReasonCode;
  label: string;
};

const VERDICT_OPTIONS: Array<{ value: FeedbackVerdict; label: string }> = [
  { value: "helpful", label: "Helpful" },
  { value: "partially_helpful", label: "Partly helpful" },
  { value: "not_helpful", label: "Not helpful" },
];

const REASON_OPTIONS: FeedbackOption[] = [
  { value: "grounding", label: "Wrong or unsupported answer" },
  { value: "retrieval", label: "Missed an important source" },
  { value: "abstain", label: "Should have said it could not answer" },
  { value: "tone", label: "Too vague or hard to read" },
  { value: "policy", label: "Policy or instruction issue" },
  { value: "other", label: "Something else" },
];

export function AnswerFeedback({ requestId, onSuccess }: Props) {
  const [verdict, setVerdict] = useState<FeedbackVerdict | null>(null);
  const [reasonCode, setReasonCode] = useState<FeedbackReasonCode>("grounding");
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setVerdict(null);
    setReasonCode("grounding");
    setComment("");
    setStatus("idle");
    setMessage(null);
  }, [requestId]);

  const isDisabled = !requestId || status === "submitting" || status === "success";
  const selectedReasonLabel = useMemo(
    () => REASON_OPTIONS.find((option) => option.value === reasonCode)?.label ?? "Other",
    [reasonCode]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!requestId || !verdict) {
      return;
    }

    setStatus("submitting");
    setMessage(null);
    try {
      await submitFeedback({
        search_query_id: requestId,
        verdict,
        reason_code: reasonCode,
        comment: comment.trim() || null,
      });
      setStatus("success");
      setMessage("Thanks, feedback saved.");
      onSuccess?.();
    } catch (exc) {
      setStatus("error");
      setMessage(normalizeErrorMessage(exc));
    }
  }

  return (
    <form className="feedback-panel" onSubmit={(event) => void handleSubmit(event)}>
      <div className="feedback-header">
        <div>
          <span>Was this helpful?</span>
          <p>Share what went wrong so we can review the answer against the retrieved sources.</p>
        </div>
      </div>

      <div className="feedback-verdicts" role="group" aria-label="Feedback verdict">
        {VERDICT_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`feedback-chip ${verdict === option.value ? "is-active" : ""}`}
            onClick={() => {
              setVerdict(option.value);
              if (option.value === "helpful") {
                setReasonCode("other");
              }
            }}
            disabled={!requestId || status === "submitting" || status === "success"}
          >
            {option.label}
          </button>
        ))}
      </div>

      <label className="feedback-field">
        <span>What best describes it?</span>
        <select
          value={reasonCode}
          onChange={(event) => setReasonCode(event.target.value as FeedbackReasonCode)}
          disabled={!requestId || status === "submitting" || status === "success"}
        >
          {REASON_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <label className="feedback-field">
        <span>Optional comment</span>
        <textarea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Add a short note for triage."
          rows={3}
          disabled={!requestId || status === "submitting" || status === "success"}
        />
      </label>

      <div className="feedback-footer">
        <button type="submit" disabled={isDisabled || verdict === null}>
          {status === "submitting" ? "Sending..." : "Send feedback"}
        </button>
        <small>
          {status === "success"
            ? message
            : verdict
              ? `Selected: ${verdict.replace("_", " ")}, ${selectedReasonLabel.toLowerCase()}`
              : "Pick one verdict to start."}
        </small>
      </div>

      {status === "error" && message ? <p className="error-message">{message}</p> : null}
    </form>
  );
}

function normalizeErrorMessage(exc: unknown): string {
  if (!(exc instanceof Error)) {
    return "Could not save feedback.";
  }

  try {
    const parsed = JSON.parse(exc.message) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      if (parsed.detail.toLowerCase().includes("feedback persistence is unavailable")) {
        return "Feedback couldn't be saved right now. Please try again later.";
      }
      if (parsed.detail.toLowerCase().includes("search history entry not found")) {
        return "Feedback isn't available for this answer.";
      }
      return parsed.detail;
    }
  } catch {
    // Fall through to the raw error message below.
  }

  if (exc.message.toLowerCase().includes("feedback persistence is unavailable")) {
    return "Feedback couldn't be saved right now. Please try again later.";
  }

  if (exc.message.toLowerCase().includes("search history entry not found")) {
    return "Feedback isn't available for this answer.";
  }

  return exc.message;
}
