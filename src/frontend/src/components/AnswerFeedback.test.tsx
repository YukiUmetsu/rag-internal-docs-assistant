import "@testing-library/jest-dom/vitest";

import { fireEvent, render, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { AnswerFeedback } from "./AnswerFeedback";
import { submitFeedback } from "../api/feedback";

vi.mock("../api/feedback", () => ({
  submitFeedback: vi.fn(),
}));

const mockedSubmitFeedback = vi.mocked(submitFeedback);

beforeEach(() => {
  mockedSubmitFeedback.mockReset();
});

it("submits normalized feedback for the current request", async () => {
  mockedSubmitFeedback.mockResolvedValue({
    id: "feedback-123",
    search_query_id: "request-123",
    request_kind: "chat",
    question: "What happened?",
    verdict: "not_helpful",
    reason_code: "grounding",
    issue_category: "grounding",
    review_status: "new",
    comment_preview: "Too vague",
    created_at: "2026-04-20T12:00:00Z",
    reviewed_at: null,
    comment: "Too vague",
    reviewed_by: null,
    promoted_eval_path: null,
    langsmith_run_id: "request-123",
  });

  const { container } = render(<AnswerFeedback requestId="request-123" />);
  const scoped = within(container);

  fireEvent.click(scoped.getAllByRole("button", { name: "Not helpful" })[0]);
  fireEvent.change(scoped.getByLabelText("Optional comment"), {
    target: { value: "Too vague" },
  });
  fireEvent.click(scoped.getByRole("button", { name: "Send feedback" }));

  await waitFor(() => {
    expect(mockedSubmitFeedback).toHaveBeenCalledWith({
      search_query_id: "request-123",
      verdict: "not_helpful",
      reason_code: "grounding",
      comment: "Too vague",
    });
  });

  expect(await scoped.findByText("Thanks, feedback saved.")).toBeInTheDocument();
});

it("shows a friendly error when persistence is unavailable", async () => {
  mockedSubmitFeedback.mockRejectedValue(
    new Error('{"detail":"Feedback persistence is unavailable"}')
  );

  const { container } = render(<AnswerFeedback requestId="request-123" />);
  const scoped = within(container);

  fireEvent.click(scoped.getAllByRole("button", { name: "Not helpful" })[0]);
  fireEvent.click(scoped.getByRole("button", { name: "Send feedback" }));

  expect(
    await scoped.findByText("Feedback couldn't be saved right now. Please try again later.")
  ).toBeInTheDocument();
});

it("shows a friendly error when the history entry is missing", async () => {
  mockedSubmitFeedback.mockRejectedValue(
    new Error('{"detail":"Search history entry not found"}')
  );

  const { container } = render(<AnswerFeedback requestId="request-123" />);
  const scoped = within(container);

  fireEvent.click(scoped.getAllByRole("button", { name: "Not helpful" })[0]);
  fireEvent.click(scoped.getByRole("button", { name: "Send feedback" }));

  expect(await scoped.findByText("Feedback isn't available for this answer.")).toBeInTheDocument();
});
