import { useEffect, useState } from "react";

import { getAdminDashboard, setAdminRetrieverBackend } from "../api/admin";
import type {
  AdminDashboardResponse,
  AdminSeriesPoint,
  RetrieverBackend,
} from "../api/types";

function formatRelativeTime(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) {
    return value;
  }

  const diffSeconds = Math.round((timestamp - Date.now()) / 1000);
  const absSeconds = Math.abs(diffSeconds);
  const direction = diffSeconds < 0 ? "ago" : "from now";

  if (absSeconds < 60) {
    return `${Math.max(absSeconds, 1)} sec ${direction}`;
  }

  const diffMinutes = Math.round(absSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes} min ${direction}`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} h ${direction}`;
  }

  const diffDays = Math.round(diffHours / 24);
  return `${diffDays} d ${direction}`;
}

function formatFileSize(value: number): string {
  if (value >= 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${Math.round(value / 1024)} KB`;
  }
  return `${value} B`;
}

function formatLatency(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)} s`;
  }
  return `${Math.round(value)} ms`;
}

function maxValue(series: AdminSeriesPoint[]): number {
  return Math.max(...series.map((point) => point.value), 1);
}

function DashboardChart({
  title,
  subtitle,
  series,
  unit,
}: {
  title: string;
  subtitle: string;
  series: AdminSeriesPoint[];
  unit: string;
}) {
  const peak = maxValue(series);

  return (
    <section className="admin-panel">
      <div className="admin-panel-header">
        <div>
          <span>{title}</span>
          <p>{subtitle}</p>
        </div>
      </div>
      <div className="bar-chart" aria-label={title}>
        {series.length ? (
          series.map((point) => (
            <div className="bar-chart-item" key={`${title}-${point.label}`}>
              <div className="bar-chart-track">
                <span
                  className="bar-chart-fill"
                  style={{
                    height: `${Math.max((point.value / peak) * 100, 10)}%`,
                  }}
                  aria-hidden="true"
                />
              </div>
              <div className="bar-chart-caption">
                <strong title={point.label}>{point.label}</strong>
                <small title={`${point.value}${unit}`}>
                  {point.value}
                  {unit}
                </small>
              </div>
            </div>
          ))
        ) : (
          <div className="empty-state">
            <p>No data yet.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function StatusPill({ label, tone }: { label: string; tone: "good" | "bad" | "warn" }) {
  return <span className={`status-pill status-pill-${tone}`}>{label}</span>;
}

function corpusTone(status: AdminDashboardResponse["corpus"]["status"]): "good" | "bad" | "warn" {
  if (status === "healthy") {
    return "good";
  }
  if (status === "broken") {
    return "bad";
  }
  return "warn";
}

function backendLabel(backend: RetrieverBackend): string {
  return backend === "postgres" ? "Postgres" : "FAISS";
}

export function AdminDashboard() {
  const [dashboard, setDashboard] = useState<AdminDashboardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [switchingBackend, setSwitchingBackend] = useState<RetrieverBackend | null>(null);

  async function loadDashboard() {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getAdminDashboard();
      setDashboard(response);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load dashboard.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  async function handleSwitchBackend(nextBackend: RetrieverBackend) {
    setSwitchingBackend(nextBackend);
    setError(null);
    try {
      await setAdminRetrieverBackend(nextBackend);
      await loadDashboard();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to switch retriever.");
    } finally {
      setSwitchingBackend(null);
    }
  }

  const activeBackend = dashboard?.retriever_backend ?? "faiss";

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
          <a href="/admin" className="nav-link is-active">
            Dashboard
          </a>
          <a href="/admin/feedback" className="nav-link">
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
            <h1>Dashboard</h1>
            <p className="section-copy">
              A quick read on corpus health, ingest activity, and what people keep asking.
            </p>
          </div>
          <div className="admin-hero-actions">
            <button
              type="button"
              onClick={() => void handleSwitchBackend("faiss")}
              disabled={switchingBackend === "faiss" || activeBackend === "faiss"}
            >
              {switchingBackend === "faiss" ? "Switching..." : "Use FAISS"}
            </button>
            <button
              type="button"
              className="secondary-action"
              onClick={() => void handleSwitchBackend("postgres")}
              disabled={switchingBackend === "postgres" || activeBackend === "postgres"}
            >
              {switchingBackend === "postgres" ? "Switching..." : "Use Postgres"}
            </button>
            <a href="/admin/uploads" className="nav-link secondary-action">
              Upload files
            </a>
          </div>
        </header>

        {isLoading ? <section className="admin-panel">Loading dashboard…</section> : null}
        {error ? (
          <section className="admin-panel">
            <div className="admin-panel-header">
              <div>
                <span>Dashboard error</span>
                <p>{error}</p>
              </div>
            </div>
          </section>
        ) : null}

        {dashboard ? (
          <>
            <section className="admin-status-strip" aria-label="System status">
              <div>
                <span className="status-label">Active retriever</span>
                <strong>{backendLabel(dashboard.retriever_backend)}</strong>
              </div>
              <div className="admin-status-card admin-status-card-emphasis">
                <span className="status-label">Corpus status</span>
                <div className="status-card-value">
                  <StatusPill
                    label={dashboard.corpus.status.replace("_", " ")}
                    tone={corpusTone(dashboard.corpus.status)}
                  />
                  <small>
                    {dashboard.corpus.active_documents.toLocaleString()} docs,{" "}
                    {dashboard.corpus.active_chunks.toLocaleString()} chunks
                  </small>
                </div>
              </div>
              <div>
                <span className="status-label">Last ingest</span>
                <strong>{formatRelativeTime(dashboard.latest_ingest_at)}</strong>
              </div>
              <div>
                <span className="status-label">Latest query</span>
                <strong>{dashboard.latest_query ?? "—"}</strong>
              </div>
            </section>

            <section className="metric-grid" aria-label="Summary stats">
              {dashboard.metrics.map((metric) => (
                <article className="metric-card" key={metric.label}>
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail}</small>
                </article>
              ))}
            </section>

            <section className="chart-grid" aria-label="Usage trends">
              <DashboardChart
                title="Search volume"
                subtitle="Queries per day over the last week"
                series={dashboard.search_volume}
                unit=""
              />
              <DashboardChart
                title="Retrieval latency"
                subtitle="Average retrieval latency by day"
                series={dashboard.latency_series}
                unit=" s"
              />
              <DashboardChart
                title="Ingest jobs"
                subtitle="Completed jobs by day"
                series={dashboard.ingest_series}
                unit=""
              />
            </section>

            <section className="split-grid">
              <section className="admin-panel">
                <div className="admin-panel-header">
                  <div>
                    <span>Top questions this week</span>
                    <p>What users are repeatedly asking right now</p>
                  </div>
                </div>
                <div className="question-list">
                  {dashboard.top_questions_week.map((question, index) => (
                    <article className="question-row" key={question.question}>
                      <div className="question-rank">{index + 1}</div>
                      <div className="question-body">
                        <strong>{question.question}</strong>
                        <span>
                          {question.count} asks this week · last asked{" "}
                          {formatRelativeTime(question.last_asked_at)} · avg{" "}
                          {formatLatency(question.avg_latency_ms)}
                        </span>
                      </div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="admin-panel">
                <div className="admin-panel-header">
                  <div>
                    <span>Top questions this month</span>
                    <p>Most repeated topics across the wider window</p>
                  </div>
                </div>
                <div className="month-list">
                  {dashboard.top_questions_month.map((question) => (
                    <div className="month-row" key={question.question}>
                      <span>{question.question}</span>
                      <strong>{question.count}</strong>
                    </div>
                  ))}
                </div>
              </section>
            </section>

            <section className="split-grid" id="jobs">
              <section className="admin-panel">
                <div className="admin-panel-header">
                  <div>
                    <span>Recent ingest jobs</span>
                    <p>What the worker has been doing lately</p>
                  </div>
                </div>
                <div className="table-list">
                  {dashboard.recent_jobs.map((job) => (
                    <article className="table-row" key={job.id}>
                      <div className="table-row-topline">
                        <strong>{job.id}</strong>
                        <StatusPill
                          label={job.status}
                          tone={job.status === "failed" ? "bad" : job.status === "queued" ? "warn" : "good"}
                        />
                      </div>
                      <div className="table-row-details">
                        <span>{job.source_type}</span>
                        <span>{job.job_mode}</span>
                        <span>{formatRelativeTime(job.started_at)}</span>
                      </div>
                      <small>{job.summary}</small>
                    </article>
                  ))}
                </div>
              </section>

              <section className="admin-panel">
                <div className="admin-panel-header">
                  <div>
                    <span>Corpus health</span>
                    <p>Quick signals that keep the retriever honest</p>
                  </div>
                </div>
                <div className="health-grid">
                  <article className="health-card">
                    <span>Orphan chunks</span>
                    <strong>{dashboard.corpus.orphan_chunks}</strong>
                  </article>
                  <article className="health-card">
                    <span>Docs without chunks</span>
                    <strong>{dashboard.corpus.documents_without_chunks}</strong>
                  </article>
                  <article className="health-card">
                    <span>Missing uploads</span>
                    <strong>{dashboard.corpus.documents_with_missing_files}</strong>
                  </article>
                  {dashboard.health_flags.map((flag) => (
                    <article className="health-card" key={flag.label}>
                      <span>{flag.label}</span>
                      <strong>{flag.value}</strong>
                    </article>
                  ))}
                </div>
              </section>
            </section>

            <section className="split-grid" id="uploads">
              <section className="admin-panel">
                <div className="admin-panel-header">
                  <div>
                    <span>Recent uploads</span>
                    <p>Files that landed most recently</p>
                  </div>
                </div>
                <div className="table-list">
                  {dashboard.recent_uploads.map((upload) => (
                    <article className="table-row" key={upload.id}>
                      <div className="table-row-topline">
                        <strong>{upload.filename}</strong>
                        <small>{formatFileSize(upload.size_bytes)}</small>
                      </div>
                      <div className="table-row-details">
                        <small>{upload.checksum}</small>
                        <small>{upload.job_id ? `job ${upload.job_id}` : "job pending"}</small>
                        <small>{formatRelativeTime(upload.created_at)}</small>
                      </div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="admin-panel">
                <div className="admin-panel-header">
                  <div>
                    <span>System summary</span>
                    <p>One glance on the moving parts that matter</p>
                  </div>
                </div>
                <div className="summary-stack">
                  <div>
                    <span>Active documents</span>
                    <strong>{dashboard.corpus.active_documents.toLocaleString()}</strong>
                  </div>
                  <div>
                    <span>Active chunks</span>
                    <strong>{dashboard.corpus.active_chunks.toLocaleString()}</strong>
                  </div>
                  <div>
                    <span>Searches this week</span>
                    <strong>
                      {dashboard.search_volume
                        .reduce((sum, point) => sum + point.value, 0)
                        .toLocaleString()}
                    </strong>
                  </div>
                  <div>
                    <span>Avg retrieval latency</span>
                    <strong>
                      {(
                        dashboard.latency_series.reduce((sum, point) => sum + point.value, 0) /
                        Math.max(dashboard.latency_series.length, 1)
                      ).toFixed(1)}{" "}
                      s
                    </strong>
                  </div>
                </div>
              </section>
            </section>
          </>
        ) : null}
      </section>
    </main>
  );
}
