import "@testing-library/jest-dom/vitest";

import { fireEvent, render, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import App from "./App";
import { sendAgentChat, sendChat } from "./api/client";

vi.mock("./api/client", () => ({
  sendAgentChat: vi.fn(),
  sendChat: vi.fn(),
}));

const mockedSendAgentChat = vi.mocked(sendAgentChat);
const mockedSendChat = vi.mocked(sendChat);

beforeEach(() => {
  mockedSendAgentChat.mockReset();
  mockedSendChat.mockReset();
  mockedSendAgentChat.mockResolvedValue({
    request_id: "request-123",
    answer: "Agent answer",
    route: "internal_docs",
    last_tool: "search_internal_docs",
    tool_calls: [
      {
        name: "search_internal_docs",
        args: { question: "What is RAG?" },
        output_preview: "Recent context found",
      },
    ],
    warnings: ["Trace warning"],
    sources: [],
    mode: "live",
  });
  mockedSendChat.mockResolvedValue({
    request_id: "request-456",
    answer: "Chat answer",
    sources: [],
    retrieval: {
      use_hybrid: true,
      use_rerank: true,
      detected_year: "2025",
      final_k: 4,
      initial_k: 12,
    },
    mode_used: "mock",
    latency_ms: 12,
    warning: null,
  });
});

it("sends live mode to the agent endpoint when agent routing is selected", async () => {
  const { container } = render(<App />);
  const scoped = within(container);

  fireEvent.change(scoped.getByLabelText("Answer mode"), {
    target: { value: "agent" },
  });
  fireEvent.change(scoped.getByPlaceholderText("What was the refund window in 2025?"), {
    target: { value: "What is RAG?" },
  });
  fireEvent.click(scoped.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(mockedSendAgentChat).toHaveBeenCalledTimes(1));
  expect(mockedSendAgentChat).toHaveBeenCalledWith({
    question: "What is RAG?",
    mode: "live",
    final_k: 4,
    include_debug: true,
    client_timezone: expect.any(String),
  });
  expect(await scoped.findByText("Agent trace")).toBeInTheDocument();
  expect(scoped.getByText("Trace warning")).toBeInTheDocument();
});

it("shows the debug panel for agent responses even when traces are stripped", async () => {
  mockedSendAgentChat.mockResolvedValueOnce({
    request_id: "request-789",
    answer: "Agent answer",
    route: "direct",
    last_tool: null,
    tool_calls: [],
    warnings: [],
    sources: [],
    mode: "mock",
  });

  const { container } = render(<App />);
  const scoped = within(container);

  fireEvent.change(scoped.getByLabelText("Answer mode"), {
    target: { value: "agent" },
  });
  fireEvent.change(scoped.getByPlaceholderText("What was the refund window in 2025?"), {
    target: { value: "What is RAG?" },
  });
  fireEvent.click(scoped.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(mockedSendAgentChat).toHaveBeenCalledTimes(1));
  expect(await scoped.findByText("Agent trace")).toBeInTheDocument();
});
