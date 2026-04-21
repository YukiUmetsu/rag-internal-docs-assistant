import "@testing-library/jest-dom/vitest";

import { waitFor, within } from "@testing-library/react";
import { fireEvent, render, screen } from "@testing-library/react";
import { it, expect, vi, beforeEach } from "vitest";

import { AnswerPanel } from "./AnswerPanel";
import { submitFeedback } from "../api/feedback";

vi.mock("../api/feedback", () => ({
  submitFeedback: vi.fn(),
}));

const mockedSubmitFeedback = vi.mocked(submitFeedback);

beforeEach(() => {
  mockedSubmitFeedback.mockReset();
});

it("opens the feedback modal from the compact trigger when history exists", async () => {
  render(
    <AnswerPanel
      response={{
        request_id: "request-123",
        answer: "The refund window in 2025 was 14 days.",
        sources: [],
        retrieval: {
          use_hybrid: true,
          use_rerank: true,
          detected_year: "2025",
          final_k: 4,
          initial_k: 12,
        },
        mode_used: "live",
        latency_ms: 123,
        warning: null,
      }}
      isLoading={false}
      error={null}
    />
  );

  await waitFor(() => {
    expect(screen.getByRole("button", { name: "Not helpful?" })).toBeInTheDocument();
  });

  expect(screen.queryByRole("button", { name: "Send feedback" })).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Not helpful?" }));

  expect(screen.getByRole("button", { name: "Send feedback" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
});

it("closes the modal and shows a non-clickable thank-you after feedback saves", async () => {
  mockedSubmitFeedback.mockResolvedValue({
    id: "feedback-123",
    search_query_id: "request-123",
    request_kind: "chat",
    question: "What was the refund window in 2025?",
    verdict: "not_helpful",
    reason_code: "grounding",
    issue_category: "grounding",
    review_status: "new",
    comment_preview: null,
    created_at: "2026-04-20T12:00:00Z",
    reviewed_at: null,
    comment: null,
    reviewed_by: null,
    promoted_eval_path: null,
    langsmith_run_id: "request-123",
  });

  const { container } = render(
    <AnswerPanel
      response={{
        request_id: "request-123",
        answer: "The refund window in 2025 was 14 days.",
        sources: [],
        retrieval: {
          use_hybrid: true,
          use_rerank: true,
          detected_year: "2025",
          final_k: 4,
          initial_k: 12,
        },
        mode_used: "live",
        latency_ms: 123,
        warning: null,
      }}
      isLoading={false}
      error={null}
    />
  );

  const scoped = within(container);

  await waitFor(() => {
    expect(scoped.getByRole("button", { name: "Not helpful?" })).toBeInTheDocument();
  });

  fireEvent.click(scoped.getByRole("button", { name: "Not helpful?" }));
  fireEvent.click(scoped.getAllByRole("button", { name: "Not helpful" })[0]);
  fireEvent.click(scoped.getByRole("button", { name: "Send feedback" }));

  await waitFor(() => {
    expect(scoped.queryByRole("dialog", { name: "Feedback form" })).not.toBeInTheDocument();
  });

  expect(scoped.getByText("Thank you for your feedback.")).toBeInTheDocument();
  expect(scoped.queryByRole("button", { name: "Thank you for your feedback." })).not.toBeInTheDocument();
  expect(scoped.queryByRole("button", { name: "Not helpful?" })).not.toBeInTheDocument();
});
