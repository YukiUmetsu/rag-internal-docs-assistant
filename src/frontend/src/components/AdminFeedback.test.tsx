import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { AdminFeedback } from "./AdminFeedback";
import { listAdminFeedback } from "../api/admin";
import { updateFeedbackReview } from "../api/feedback";

vi.mock("../api/admin", () => ({
  listAdminFeedback: vi.fn(),
}));

vi.mock("../api/feedback", () => ({
  updateFeedbackReview: vi.fn(),
}));

const mockedListAdminFeedback = vi.mocked(listAdminFeedback);
const mockedUpdateFeedbackReview = vi.mocked(updateFeedbackReview);

beforeEach(() => {
  mockedListAdminFeedback.mockResolvedValue({
    items: [
      {
        id: "feedback-new",
        search_query_id: "request-new",
        request_kind: "chat",
        question: "What was the refund window in 2025?",
        verdict: "not_helpful",
        reason_code: "grounding",
        issue_category: "grounding",
        review_status: "new",
        comment_preview: "Too vague",
        created_at: "2026-04-20T12:00:00.000Z",
        reviewed_at: null,
      },
      {
        id: "feedback-triaged",
        search_query_id: "request-triaged",
        request_kind: "chat",
        question: "How are duplicate refunds handled?",
        verdict: "partially_helpful",
        reason_code: "retrieval",
        issue_category: "retrieval",
        review_status: "triaged",
        comment_preview: "Missing a source",
        created_at: "2026-04-20T12:30:00.000Z",
        reviewed_at: "2026-04-20T13:00:00.000Z",
      },
      {
        id: "feedback-promoted",
        search_query_id: "request-promoted",
        request_kind: "chat",
        question: "What is the escalation path?",
        verdict: "helpful",
        reason_code: "policy",
        issue_category: "policy",
        review_status: "promoted",
        comment_preview: "Clear answer",
        created_at: "2026-04-20T13:30:00.000Z",
        reviewed_at: "2026-04-20T14:00:00.000Z",
      },
      {
        id: "feedback-ignored",
        search_query_id: "request-ignored",
        request_kind: "chat",
        question: "What is the escalation path?",
        verdict: "not_helpful",
        reason_code: "other",
        issue_category: "other",
        review_status: "ignored",
        comment_preview: "Duplicate",
        created_at: "2026-04-20T14:30:00.000Z",
        reviewed_at: "2026-04-20T15:00:00.000Z",
      },
    ],
    total: 4,
    limit: 25,
    offset: 0,
  });
  mockedUpdateFeedbackReview.mockResolvedValue({
    id: "feedback-new",
    search_query_id: "request-new",
    request_kind: "chat",
    question: "What was the refund window in 2025?",
    verdict: "not_helpful",
    reason_code: "grounding",
    issue_category: "grounding",
    review_status: "triaged",
    comment_preview: "Too vague",
    created_at: "2026-04-20T12:00:00.000Z",
    reviewed_at: "2026-04-20T13:10:00.000Z",
    comment: "Too vague",
    reviewed_by: "reviewer@example.com",
    promoted_eval_path: null,
    langsmith_run_id: "request-new",
  });
});

it("hides the triage action for already triaged feedback", async () => {
  render(<AdminFeedback />);

  await waitFor(() => expect(mockedListAdminFeedback).toHaveBeenCalledTimes(1));

  const newRow = screen.getByText("What was the refund window in 2025?").closest("article");
  const triagedRow = screen.getByText("How are duplicate refunds handled?").closest("article");

  expect(newRow).not.toBeNull();
  expect(triagedRow).not.toBeNull();

  expect(within(newRow as HTMLElement).getByRole("button", { name: "Mark triaged" })).toBeInTheDocument();
  expect(within(triagedRow as HTMLElement).queryByRole("button", { name: "Mark triaged" })).not.toBeInTheDocument();
  expect(within(triagedRow as HTMLElement).getByRole("button", { name: "Promote" })).toBeInTheDocument();
  expect(within(triagedRow as HTMLElement).getByRole("button", { name: "Ignore" })).toBeInTheDocument();
  expect(within(triagedRow as HTMLElement).getByRole("button", { name: "Move to needs review" })).toBeInTheDocument();

  const repeatedQuestionRows = screen.getAllByText("What is the escalation path?");
  const promotedRow = repeatedQuestionRows[0].closest("article");
  expect(promotedRow).not.toBeNull();
  expect(within(promotedRow as HTMLElement).queryByRole("button", { name: "Mark triaged" })).not.toBeInTheDocument();
  expect(within(promotedRow as HTMLElement).queryByRole("button", { name: "Promote" })).not.toBeInTheDocument();
  expect(within(promotedRow as HTMLElement).queryByRole("button", { name: "Ignore" })).not.toBeInTheDocument();
  expect(within(promotedRow as HTMLElement).getByRole("button", { name: "Move to needs review" })).toBeInTheDocument();

  const ignoredRow = repeatedQuestionRows[1].closest("article");
  expect(ignoredRow).not.toBeNull();
  expect(within(ignoredRow as HTMLElement).queryByRole("button", { name: "Mark triaged" })).not.toBeInTheDocument();
  expect(within(ignoredRow as HTMLElement).queryByRole("button", { name: "Promote" })).not.toBeInTheDocument();
  expect(within(ignoredRow as HTMLElement).queryByRole("button", { name: "Ignore" })).not.toBeInTheDocument();
  expect(within(ignoredRow as HTMLElement).getByRole("button", { name: "Move to needs review" })).toBeInTheDocument();

  fireEvent.click(within(newRow as HTMLElement).getByRole("button", { name: "Mark triaged" }));

  await waitFor(() => expect(mockedUpdateFeedbackReview).toHaveBeenCalledTimes(1));
  expect(mockedUpdateFeedbackReview).toHaveBeenCalledWith("feedback-new", { review_status: "triaged" });
});
