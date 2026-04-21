import { useEffect, useState } from "react";
import type { ChatResponse } from "../api/types";
import { AnswerFeedback } from "./AnswerFeedback";

type Props = {
  response: ChatResponse | null;
  isLoading: boolean;
  error: string | null;
};

const LOADING_STEPS = ["Retrieving sources", "Ranking passages", "Preparing response"];

export function AnswerPanel({ response, isLoading, error }: Props) {
  const [loadingIndex, setLoadingIndex] = useState(0);
  const [dotCount, setDotCount] = useState(1);
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      setLoadingIndex(0);
      setDotCount(1);
      return undefined;
    }

    const intervalId = window.setInterval(() => {
      setDotCount((currentDots) => {
        if (currentDots === 3) {
          setLoadingIndex((currentIndex) => (currentIndex + 1) % LOADING_STEPS.length);
          return 1;
        }
        return currentDots + 1;
      });
    }, 420);

    return () => window.clearInterval(intervalId);
  }, [isLoading]);

  useEffect(() => {
    setIsFeedbackOpen(false);
    setFeedbackSubmitted(false);
  }, [response?.request_id]);

  return (
    <section className="answer-panel">
      <div className="panel-header">
        <span>Answer</span>
        {response ? <small>{response.mode_used.replace("_", " ")}</small> : null}
      </div>

      {isLoading ? (
        <div className="loading-stack" aria-live="polite">
          <span className="loading-line">
            {LOADING_STEPS[loadingIndex]}
            {".".repeat(dotCount)}
          </span>
        </div>
      ) : null}

      {error ? <p className="error-message">{error}</p> : null}

      {!isLoading && !error && response ? (
        <>
          {response.warning ? <p className="warning-message">{response.warning}</p> : null}
          <p className="answer-text">{response.answer}</p>
          {response.request_id ? (
            <div className="feedback-trigger-row">
              {feedbackSubmitted ? (
                <span className="feedback-thanks">
                  <span className="feedback-thanks-icon" aria-hidden="true">
                    ✓
                  </span>
                  Thank you for your feedback.
                </span>
              ) : (
                <button
                  type="button"
                  className="feedback-trigger"
                  onClick={() => setIsFeedbackOpen(true)}
                >
                  Not helpful?
                </button>
              )}
            </div>
          ) : null}
        </>
      ) : null}

      {!isLoading && !error && response && isFeedbackOpen && response.request_id ? (
        <div
          className="feedback-modal-backdrop"
          role="presentation"
          onClick={() => setIsFeedbackOpen(false)}
        >
          <div
            className="feedback-modal"
            role="dialog"
            aria-modal="true"
            aria-label="Feedback form"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="feedback-modal-close"
              onClick={() => setIsFeedbackOpen(false)}
            >
              Close
            </button>
            <AnswerFeedback
              requestId={response.request_id}
              onSuccess={() => {
                setFeedbackSubmitted(true);
                setIsFeedbackOpen(false);
              }}
            />
          </div>
        </div>
      ) : null}

      {!isLoading && !error && !response ? (
        <p className="empty-answer">
          Ask about policies, incidents, support playbooks, or engineering docs.
        </p>
      ) : null}
    </section>
  );
}
