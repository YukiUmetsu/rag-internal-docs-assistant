import { expect, it, vi } from "vitest";

import { sendAgentChat } from "./client";
import { requestJson } from "./request";

vi.mock("./request", () => ({
  requestJson: vi.fn(),
}));

it("sends agent chat requests to the agent endpoint", async () => {
  vi.mocked(requestJson).mockResolvedValueOnce({
    request_id: "request-123",
    answer: "Agent answer",
    route: "internal_docs",
    last_tool: "search_internal_docs",
    tool_calls: [],
    warnings: [],
    sources: [],
    mode: "mock",
  });

  await sendAgentChat({
    question: "What is the refund window?",
    mode: "mock",
    final_k: 4,
    include_debug: true,
  });

  expect(requestJson).toHaveBeenCalledWith("/api/agent/chat", {
    method: "POST",
    body: JSON.stringify({
      question: "What is the refund window?",
      mode: "mock",
      final_k: 4,
      include_debug: true,
    }),
  });
});
