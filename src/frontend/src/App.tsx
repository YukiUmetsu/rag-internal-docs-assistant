import { useState } from "react";

import { sendChat } from "./api/client";
import type { ChatResponse, RequestMode } from "./api/types";
import { AdminDashboard } from "./components/AdminDashboard";
import { AdminIngestJobs } from "./components/AdminIngestJobs";
import { AdminUploads } from "./components/AdminUploads";
import { AnswerPanel } from "./components/AnswerPanel";
import { ChatComposer } from "./components/ChatComposer";
import { ExamplePrompts } from "./components/ExamplePrompts";
import { RetrievalDebugPanel } from "./components/RetrievalDebugPanel";

export default function App() {
  const pathname = window.location.pathname;

  if (pathname.startsWith("/admin/jobs")) {
    return <AdminIngestJobs />;
  }

  if (pathname.startsWith("/admin/uploads")) {
    return <AdminUploads />;
  }

  if (pathname.startsWith("/admin")) {
    return <AdminDashboard />;
  }

  const [question, setQuestion] = useState("");
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
      <nav className="top-nav" aria-label="Primary">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <span>Acme Assistant</span>
        </div>
        <div className="nav-links" aria-label="Demo context">
          <span>Docs</span>
          <span>Retrieval</span>
          <span>API</span>
          <a href="/admin" className="nav-link">
            Admin
          </a>
          <a href="/admin/uploads" className="nav-link">
            Uploads
          </a>
        </div>
      </nav>

      <section className="workspace">
        <section className="prompt-stage" aria-label="Assistant search">
          <header className="app-header">
            <p>Internal knowledge search</p>
          </header>

          <div className="prompt-console">
            <ChatComposer
              question={question}
              mode={mode}
              isLoading={isLoading}
              onQuestionChange={setQuestion}
              onModeChange={setMode}
              onSubmit={handleSubmit}
            />
          </div>

          <ExamplePrompts onSelect={setQuestion} />
        </section>

        <div className="content-grid">
          <section className="conversation">
            <AnswerPanel response={response} isLoading={isLoading} error={error} />
            {response?.sources.length ? <RetrievalDebugPanel response={response} /> : null}
          </section>
        </div>
      </section>
    </main>
  );
}
