import { useEffect, useMemo, useState } from "react";

import { getAdminJobDetail, listAdminJobs } from "../api/admin";
import { PaginationControls } from "./PaginationControls";
import type {
  AdminJobSortKey,
  AdminJobStat,
  IngestJobDetail,
  SortDirection,
} from "../api/types";

type TimeRange = "today" | "7d" | "30d";

const PAGE_SIZE = 4;
const TIME_RANGE_DAYS: Record<TimeRange, number> = {
  today: 1,
  "7d": 7,
  "30d": 30,
};

const timeFilters: { key: TimeRange; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
];

function statusTone(status: string): "good" | "bad" | "warn" {
  if (status === "failed") {
    return "bad";
  }
  if (status === "queued") {
    return "warn";
  }
  return "good";
}

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

function SortButton({
  active,
  direction,
  label,
  onClick,
}: {
  active: boolean;
  direction: SortDirection;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`upload-sort-button${active ? " is-active" : ""}`}
      onClick={onClick}
      aria-label={`Sort by ${label}`}
    >
      <span>{label}</span>
      <small>{active ? (direction === "asc" ? "↑" : "↓") : "↕"}</small>
    </button>
  );
}

function StatusPill({ label, tone }: { label: string; tone: "good" | "bad" | "warn" }) {
  return <span className={`status-pill status-pill-${tone}`}>{label}</span>;
}

function sortKeyToApiKey(key: SortKey): AdminJobSortKey {
  switch (key) {
    case "source":
      return "source_type";
    case "mode":
      return "job_mode";
    case "status":
      return "status";
    case "startedAt":
      return "started_at";
    case "finishedAt":
      return "finished_at";
    case "docs":
      return "source_documents";
    case "chunks":
      return "chunks";
    case "id":
    default:
      return "id";
  }
}

type SortKey = "id" | "source" | "mode" | "status" | "startedAt" | "finishedAt" | "docs" | "chunks";

type SummaryCard = {
  label: string;
  value: string;
  detail: string;
};

function summarizeJobs(jobs: AdminJobStat[], total: number): SummaryCard[] {
  const queued = jobs.filter((job) => job.status === "queued").length;
  const running = jobs.filter((job) => job.status === "running").length;
  const failed = jobs.filter((job) => job.status === "failed").length;
  return [
    { label: "Jobs in window", value: String(total), detail: "Across the selected period" },
    { label: "Queued jobs", value: String(queued), detail: "Waiting for worker pickup" },
    { label: "Running jobs", value: String(running), detail: "In flight right now" },
    { label: "Failed on page", value: String(failed), detail: "Needs attention" },
  ];
}

export function AdminIngestJobs() {
  const [jobs, setJobs] = useState<AdminJobStat[]>([]);
  const [total, setTotal] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>("startedAt");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<IngestJobDetail | null>(null);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadJobs(nextPage = page, nextSortKey = sortKey, nextSortDirection = sortDirection, nextRange = timeRange) {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listAdminJobs({
        limit: PAGE_SIZE,
        offset: (nextPage - 1) * PAGE_SIZE,
        sortBy: sortKeyToApiKey(nextSortKey),
        sortDir: nextSortDirection,
        days: TIME_RANGE_DAYS[nextRange],
      });
      setJobs(response.items);
      setTotal(response.total);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load ingest jobs.");
      setJobs([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadJobs(page, sortKey, sortDirection, timeRange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, sortKey, sortDirection, timeRange]);

  useEffect(() => {
    if (!selectedJobId) {
      setSelectedJob(null);
      return;
    }

    let cancelled = false;
    setSelectedJob(null);
    setIsDetailLoading(true);
    getAdminJobDetail(selectedJobId)
      .then((detail) => {
        if (!cancelled) {
          setSelectedJob(detail);
        }
      })
      .catch((exc) => {
        if (!cancelled) {
          setError(exc instanceof Error ? exc.message : "Failed to load job details.");
          setSelectedJob(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsDetailLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedJobId]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageStart = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const pageEnd = total === 0 ? 0 : Math.min(currentPage * PAGE_SIZE, total);
  const summaryCards = useMemo(() => summarizeJobs(jobs, total), [jobs, total]);

  function resetSelection() {
    setSelectedJobId(null);
    setSelectedJob(null);
  }

  function setTimeRangeAndReset(nextRange: TimeRange) {
    setTimeRange(nextRange);
    setPage(1);
    resetSelection();
  }

  function toggleSort(key: SortKey) {
    setPage(1);
    resetSelection();
    setSortKey((currentKey) => {
      if (currentKey === key) {
        setSortDirection((currentDirection) => (currentDirection === "asc" ? "desc" : "asc"));
        return currentKey;
      }
      setSortDirection("desc");
      return key;
    });
  }

  function selectPage(nextPage: number) {
    setPage(nextPage);
    resetSelection();
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
          <a href="/admin/uploads" className="nav-link">
            Uploads
          </a>
          <a href="/admin/jobs" className="nav-link is-active">
            Ingest Jobs
          </a>
        </div>
      </nav>

      <section className="admin-layout">
        <header className="admin-hero">
          <div>
            <p className="section-kicker">Ingest Jobs</p>
            <h1>Worker runs and their outcomes</h1>
            <p className="section-copy">
              A control-room view for ingest activity: what ran, what&apos;s running, and what needs a
              second look.
            </p>
          </div>
        </header>

        <section className="metric-grid" aria-label="Ingest summary">
          {summaryCards.map((card) => (
            <article className="metric-card" key={card.label}>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <small>{card.detail}</small>
            </article>
          ))}
        </section>

        <section className="table-toolbar">
          <p>
            Showing {pageStart}-{pageEnd} of {total}
          </p>
          <div className="pagination-controls" aria-label="Time range filters">
            {timeFilters.map((filter) => (
              <button
                key={filter.key}
                type="button"
                className={timeRange === filter.key ? "is-active" : ""}
                onClick={() => setTimeRangeAndReset(filter.key)}
              >
                {filter.label}
                </button>
              ))}
            </div>
        </section>

        <section className="ingest-jobs-layout">
          <section className="admin-panel ingest-job-table-panel">
            <div className="admin-panel-header">
              <div>
                <span>Recent jobs</span>
                <p>Sortable table of the latest worker runs</p>
              </div>
            </div>

            {isLoading ? <div className="empty-state">Loading jobs…</div> : null}
            {error ? <div className="empty-state">{error}</div> : null}

            {!isLoading && !error ? (
              <>
                <div className="table-card">
          <table className="upload-table ingest-job-table">
                    <thead>
                      <tr className="upload-table-head">
                        <th>
                          <SortButton
                            active={sortKey === "id"}
                            direction={sortDirection}
                            label="Job"
                            onClick={() => toggleSort("id")}
                          />
                        </th>
                        <th>
                          <SortButton
                            active={sortKey === "source"}
                            direction={sortDirection}
                            label="Source"
                            onClick={() => toggleSort("source")}
                          />
                        </th>
                        <th>
                          <SortButton
                            active={sortKey === "mode"}
                            direction={sortDirection}
                            label="Mode"
                            onClick={() => toggleSort("mode")}
                          />
                        </th>
                        <th>
                          <SortButton
                            active={sortKey === "status"}
                            direction={sortDirection}
                            label="Status"
                            onClick={() => toggleSort("status")}
                          />
                        </th>
                        <th>
                          <SortButton
                            active={sortKey === "startedAt"}
                            direction={sortDirection}
                            label="Started"
                            onClick={() => toggleSort("startedAt")}
                          />
                        </th>
                        <th>
                          <SortButton
                            active={sortKey === "finishedAt"}
                            direction={sortDirection}
                            label="Finished"
                            onClick={() => toggleSort("finishedAt")}
                          />
                        </th>
                        <th>
                          <SortButton
                            active={sortKey === "docs"}
                            direction={sortDirection}
                            label="Docs"
                            onClick={() => toggleSort("docs")}
                          />
                        </th>
                        <th>
                          <SortButton
                            active={sortKey === "chunks"}
                            direction={sortDirection}
                            label="Chunks"
                            onClick={() => toggleSort("chunks")}
                          />
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {jobs.map((job) => (
                        <tr
                          key={job.id}
                          className={`upload-table-row${job.id === selectedJob?.id ? " is-selected" : ""}`}
                          onClick={() => setSelectedJobId(job.id)}
                        >
                          <td>
                            <strong>{job.id}</strong>
                          </td>
                          <td>{job.source_type}</td>
                          <td>{job.job_mode}</td>
                          <td>
                            <StatusPill label={job.status} tone={statusTone(job.status)} />
                          </td>
                          <td>{formatRelativeTime(job.started_at)}</td>
                          <td>{formatRelativeTime(job.finished_at)}</td>
                          <td>{job.source_documents}</td>
                          <td>{job.chunks}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="pagination-footer">
                  <p>
                    Page {currentPage} of {totalPages}
                  </p>
                  <PaginationControls
                    currentPage={currentPage}
                    totalPages={totalPages}
                    onPageChange={selectPage}
                    ariaLabel="Job table pagination"
                  />
                </div>
              </>
            ) : null}
          </section>

          {selectedJobId ? (
            <>
              <button
                type="button"
                className="ingest-job-backdrop"
                aria-label="Close selected job details"
                onClick={() => resetSelection()}
              />
              <aside className="admin-panel ingest-job-drawer">
                <div className="admin-panel-header ingest-job-drawer-header">
                  <div>
                    <span>Selected job</span>
                    <p>Details for the highlighted worker run</p>
                  </div>
                  <button
                    type="button"
                    className="drawer-close-button"
                    aria-label="Close selected job details"
                    onClick={() => resetSelection()}
                  >
                    Close
                  </button>
                </div>

                {isDetailLoading ? <div className="empty-state">Loading job details…</div> : null}

                {selectedJob && !isDetailLoading ? (
                  <div className="detail-stack">
                    <section className="detail-card detail-card-status">
                      <div className="detail-card-header">
                        <span>{selectedJob.id}</span>
                        <StatusPill label={selectedJob.status} tone={statusTone(selectedJob.status)} />
                      </div>
                      <small>
                        {selectedJob.source_type} · {selectedJob.job_mode} ·{" "}
                        {formatRelativeTime(selectedJob.started_at)}
                      </small>
                    </section>

                    <section className="detail-card">
                      <span>Summary</span>
                      <strong>{selectedJob.result_message ?? selectedJob.error_message ?? "No summary yet."}</strong>
                      <p>{selectedJob.error_message ?? selectedJob.result_message ?? "No details available."}</p>
                    </section>

                    <section className="detail-card">
                      <span>Inputs</span>
                      <div className="detail-list">
                        <div>
                          <small>Requested paths</small>
                          <strong>
                            {selectedJob.requested_paths.length ? selectedJob.requested_paths.join(", ") : "None"}
                          </strong>
                        </div>
                        <div>
                          <small>Uploaded file ids</small>
                          <strong>
                            {selectedJob.uploaded_file_ids.length
                              ? selectedJob.uploaded_file_ids.join(", ")
                              : "None"}
                          </strong>
                        </div>
                        <div>
                          <small>Task id</small>
                          <strong>{selectedJob.task_id ?? "None"}</strong>
                        </div>
                      </div>
                    </section>

                    <section className="detail-card">
                      <span>Counts</span>
                      <div className="detail-metric-row">
                        <div>
                          <small>Started</small>
                          <strong>{formatRelativeTime(selectedJob.started_at)}</strong>
                        </div>
                        <div>
                          <small>Finished</small>
                          <strong>{formatRelativeTime(selectedJob.finished_at)}</strong>
                        </div>
                        <div>
                          <small>State</small>
                          <strong>{selectedJob.status}</strong>
                        </div>
                      </div>
                    </section>
                  </div>
                ) : null}
              </aside>
            </>
          ) : null}
        </section>
      </section>
    </main>
  );
}
