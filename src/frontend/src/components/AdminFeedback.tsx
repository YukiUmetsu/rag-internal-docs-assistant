import { useEffect, useState } from "react";

import { listAdminFeedback } from "../api/admin";
import { updateFeedbackReview } from "../api/feedback";
import type { FeedbackReviewStatus, FeedbackSummary } from "../api/types";

const REVIEW_FILTERS: Array<{ label: string; value: FeedbackReviewStatus | "all" }> = [
  { label: "Needs review", value: "new" },
  { label: "Promoted", value: "promoted" },
  { label: "Triaged", value: "triaged" },
  { label: "Ignored", value: "ignored" },
  { label: "All", value: "all" },
];

const REVIEW_STATUS_LABELS: Record<FeedbackReviewStatus, string> = {
  new: "Needs review",
  triaged: "Triaged",
  promoted: "Promoted",
  ignored: "Ignored",
};

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function FeedbackRow({
  item,
  onChange,
  busy,
}: {
  item: FeedbackSummary;
  onChange: (feedbackId: string, nextStatus: FeedbackReviewStatus) => Promise<void>;
  busy: boolean;
}) {
  const canTriage = item.review_status === "new";
  const canPromote = item.review_status === "new" || item.review_status === "triaged";
  const canIgnore = item.review_status === "new" || item.review_status === "triaged";
  const canMoveToNeedsReview = item.review_status !== "new";

  return (
    <article className="feedback-row">
      <div className="feedback-row-head">
        <div>
          <strong>{item.question}</strong>
          <p>
            {item.request_kind} · {item.verdict.replace("_", " ")} · {item.reason_code}
          </p>
        </div>
        <span
          className={`status-pill status-pill-${
            item.review_status === "promoted"
              ? "good"
              : item.review_status === "ignored"
                ? "bad"
                : "warn"
          }`}
        >
          {REVIEW_STATUS_LABELS[item.review_status]}
        </span>
      </div>
      <p className="feedback-comment">
        {item.comment_preview ?? "No comment provided."}
      </p>
      <div className="feedback-row-meta">
        <small>Created {formatDate(item.created_at)}</small>
        <small>Reviewed {formatDate(item.reviewed_at)}</small>
      </div>
      <div className="feedback-row-actions">
        {canTriage ? (
          <button
            type="button"
            disabled={busy}
            className="feedback-action feedback-action-emphasis"
            onClick={() => void onChange(item.id, "triaged")}
          >
            Mark triaged
          </button>
        ) : null}
        {canPromote ? (
          <button
            type="button"
            disabled={busy}
            className="feedback-action"
            onClick={() => void onChange(item.id, "promoted")}
          >
            Promote
          </button>
        ) : null}
        {canIgnore ? (
          <button
            type="button"
            disabled={busy}
            className="feedback-action"
            onClick={() => void onChange(item.id, "ignored")}
          >
            Ignore
          </button>
        ) : null}
        {canMoveToNeedsReview ? (
          <button
            type="button"
            disabled={busy}
            className="feedback-action feedback-action-subtle"
            onClick={() => void onChange(item.id, "new")}
          >
            Move to needs review
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function AdminFeedback() {
  const [items, setItems] = useState<FeedbackSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<FeedbackReviewStatus | "all">("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function loadFeedback(nextFilter: FeedbackReviewStatus | "all" = filter) {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listAdminFeedback({
        limit: 25,
        offset: 0,
        reviewStatus: nextFilter === "all" ? undefined : nextFilter,
      });
      setItems(response.items);
      setTotal(response.total);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load feedback.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadFeedback(filter);
  }, [filter]);

  async function handleReviewChange(feedbackId: string, nextStatus: FeedbackReviewStatus) {
    setBusyId(feedbackId);
    setError(null);
    try {
      await updateFeedbackReview(feedbackId, { review_status: nextStatus });
      await loadFeedback(filter);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to update feedback.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <main className="app-shell admin-shell">
      <nav className="top-nav admin-top-nav" aria-label="Primary">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <span>Acme Assistant Admin</span>
        </div>
        <div className="nav-links" aria-label="Workspace switcher">
          <a href="/" className="nav-link">
            Assistant
          </a>
          <a href="/admin" className="nav-link">
            Dashboard
          </a>
          <a href="/admin/feedback" className="nav-link is-active">
            Feedback
          </a>
          <a href="/admin/uploads" className="nav-link">
            Uploads
          </a>
          <a href="/admin/jobs" className="nav-link">
            Ingest Jobs
          </a>
        </div>
      </nav>

      <section className="admin-layout">
        <header className="admin-hero">
          <div>
            <p className="section-kicker">Operations</p>
            <h1>Feedback queue</h1>
            <p className="section-copy">
              Review user feedback and promote high-signal cases into the eval workflow.
            </p>
          </div>
          <div className="admin-hero-actions">
            <button type="button" onClick={() => void loadFeedback(filter)}>
              Refresh
            </button>
          </div>
        </header>

        <section className="admin-panel">
          <div className="admin-panel-header">
            <div>
              <span>Queue</span>
              <p>{total.toLocaleString()} feedback item(s)</p>
            </div>
          </div>
          <div className="feedback-filter-row" role="group" aria-label="Feedback status filter">
            {REVIEW_FILTERS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={filter === option.value ? "is-active" : ""}
                onClick={() => setFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </section>

        {isLoading ? <section className="admin-panel">Loading feedback…</section> : null}
        {error ? (
          <section className="admin-panel">
            <div className="admin-panel-header">
              <div>
                <span>Feedback error</span>
                <p>{error}</p>
              </div>
            </div>
          </section>
        ) : null}

        {!isLoading && !error ? (
          <section className="feedback-list">
            {items.length ? (
              items.map((item) => (
                <FeedbackRow
                  key={item.id}
                  item={item}
                  onChange={handleReviewChange}
                  busy={busyId === item.id}
                />
              ))
            ) : (
              <div className="admin-panel">
                <div className="empty-state">No feedback matches this filter.</div>
              </div>
            )}
          </section>
        ) : null}
      </section>
    </main>
  );
}
