import { requestJson } from "./request";
import type { FeedbackCreateRequest, FeedbackDetail, FeedbackReviewUpdateRequest } from "./types";

export function submitFeedback(payload: FeedbackCreateRequest): Promise<FeedbackDetail> {
  return requestJson<FeedbackDetail>("/api/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateFeedbackReview(
  feedbackId: string,
  payload: FeedbackReviewUpdateRequest
): Promise<FeedbackDetail> {
  return requestJson<FeedbackDetail>(`/api/admin/feedback/${feedbackId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}
