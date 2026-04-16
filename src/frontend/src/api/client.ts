import type { ChatRequest, ChatResponse, HealthResponse, RetrieveResponse } from "./types";
import { requestJson } from "./request";

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health");
}

export function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  return requestJson<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function retrieveSources(payload: ChatRequest): Promise<RetrieveResponse> {
  return requestJson<RetrieveResponse>("/api/retrieve", {
    method: "POST",
    body: JSON.stringify({ ...payload, mode: "retrieve_only" })
  });
}
