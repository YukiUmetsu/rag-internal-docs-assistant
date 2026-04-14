import { useState } from "react";

import { sendChat } from "./api/client";
import type { ChatResponse, RequestMode } from "./api/types";
import { AnswerPanel } from "./components/AnswerPanel";
import { ChatComposer } from "./components/ChatComposer";
import { ExamplePrompts } from "./components/ExamplePrompts";
import { RetrievalDebugPanel } from "./components/RetrievalDebugPanel";

const DEFAULT_PROMPT = "What was the refund window in 2025?";

export default function App() {
  const [question, setQuestion] = useState(DEFAULT_PROMPT);
  const [mode, setMode] = useState<RequestMode>("mock");
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const result = await sendChat({
        question: trimmedQuestion,
        mode,
        final_k: 4
      });
      setResponse(result);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Something went wrong.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="app-header">
          <p>Acme internal knowledge</p>
          <h1>Ask internal docs</h1>
        </header>

        <div className="content-grid">
          <section className="conversation">
            <ChatComposer
              question={question}
              mode={mode}
              isLoading={isLoading}
              onQuestionChange={setQuestion}
              onModeChange={setMode}
              onSubmit={handleSubmit}
            />
            <ExamplePrompts onSelect={setQuestion} />
            <AnswerPanel response={response} isLoading={isLoading} error={error} />
          </section>

          <RetrievalDebugPanel response={response} />
        </div>
      </section>
    </main>
  );
}
