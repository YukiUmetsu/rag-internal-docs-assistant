import { useMemo, useState } from "react";

type JobStatus = "Succeeded" | "Running" | "Queued" | "Failed";
type JobSource = "mounted_data" | "uploaded_files" | "validation";
type JobMode = "full" | "partial" | "validation";
type TimeRange = "today" | "7d" | "30d";
type SortKey = "id" | "source" | "mode" | "status" | "startedAt" | "finishedAt" | "docs" | "chunks";
type SortDirection = "asc" | "desc";

type IngestJob = {
  id: string;
  source: JobSource;
  mode: JobMode;
  status: JobStatus;
  startedAt: string;
  finishedAt: string;
  sourceDocuments: number;
  chunks: number;
  summary: string;
  requestedPaths: string[];
  uploadedFileIds: string[];
  taskId: string;
  resultMessage: string;
  errorMessage: string | null;
};

const jobs: IngestJob[] = [
  {
    id: "job-46",
    source: "mounted_data",
    mode: "full",
    status: "Succeeded",
    startedAt: "8 min ago",
    finishedAt: "6 min ago",
    sourceDocuments: 3,
    chunks: 42,
    summary: "Mounted corpus refreshed successfully.",
    requestedPaths: ["data/"],
    uploadedFileIds: [],
    taskId: "job-46",
    resultMessage: "Ingested 3 source document(s), inserted 42 chunk(s).",
    errorMessage: null,
  },
  {
    id: "job-45",
    source: "uploaded_files",
    mode: "partial",
    status: "Succeeded",
    startedAt: "32 min ago",
    finishedAt: "29 min ago",
    sourceDocuments: 2,
    chunks: 18,
    summary: "Uploaded docs were added to the active corpus.",
    requestedPaths: [],
    uploadedFileIds: ["upload-18", "upload-19"],
    taskId: "job-45",
    resultMessage: "Ingested 2 uploaded file(s), inserted 18 chunk(s).",
    errorMessage: null,
  },
  {
    id: "job-44",
    source: "validation",
    mode: "validation",
    status: "Succeeded",
    startedAt: "58 min ago",
    finishedAt: "57 min ago",
    sourceDocuments: 0,
    chunks: 0,
    summary: "Smoke-tested the ingest queue and worker path.",
    requestedPaths: ["data/"],
    uploadedFileIds: [],
    taskId: "job-44",
    resultMessage: "Validation completed successfully.",
    errorMessage: null,
  },
  {
    id: "job-43",
    source: "mounted_data",
    mode: "full",
    status: "Running",
    startedAt: "9 min ago",
    finishedAt: "in progress",
    sourceDocuments: 1,
    chunks: 12,
    summary: "Currently ingesting mounted docs.",
    requestedPaths: ["data/engineering", "data/hr"],
    uploadedFileIds: [],
    taskId: "job-43",
    resultMessage: "Processing source documents in the worker.",
    errorMessage: null,
  },
  {
    id: "job-42",
    source: "uploaded_files",
    mode: "partial",
    status: "Queued",
    startedAt: "2 min ago",
    finishedAt: "pending",
    sourceDocuments: 0,
    chunks: 0,
    summary: "Awaiting worker pickup.",
    requestedPaths: [],
    uploadedFileIds: ["upload-17"],
    taskId: "job-42",
    resultMessage: "Queued for processing.",
    errorMessage: null,
  },
  {
    id: "job-41",
    source: "mounted_data",
    mode: "full",
    status: "Succeeded",
    startedAt: "1 h ago",
    finishedAt: "1 h ago",
    sourceDocuments: 4,
    chunks: 51,
    summary: "Mounted corpus refreshed after a policy change.",
    requestedPaths: ["data/"],
    uploadedFileIds: [],
    taskId: "job-41",
    resultMessage: "Ingested 4 source document(s), inserted 51 chunk(s).",
    errorMessage: null,
  },
  {
    id: "job-40",
    source: "uploaded_files",
    mode: "partial",
    status: "Succeeded",
    startedAt: "3 h ago",
    finishedAt: "3 h ago",
    sourceDocuments: 1,
    chunks: 7,
    summary: "Uploaded handbook processed cleanly.",
    requestedPaths: [],
    uploadedFileIds: ["upload-15"],
    taskId: "job-40",
    resultMessage: "Ingested 1 uploaded file, inserted 7 chunk(s).",
    errorMessage: null,
  },
  {
    id: "job-39",
    source: "mounted_data",
    mode: "full",
    status: "Failed",
    startedAt: "6 h ago",
    finishedAt: "6 h ago",
    sourceDocuments: 0,
    chunks: 0,
    summary: "PDF parse timed out.",
    requestedPaths: ["data/incidents"],
    uploadedFileIds: [],
    taskId: "job-39",
    resultMessage: "Ingest failed before corpus update.",
    errorMessage: "PDF parse timed out while reading incident-runbook.pdf",
  },
];

const summaryCards = [
  { label: "Queued jobs", value: "1", detail: "Waiting for worker pickup" },
  { label: "Running jobs", value: "1", detail: "In flight right now" },
  { label: "Succeeded today", value: "3", detail: "Clean worker runs" },
  { label: "Failed today", value: "1", detail: "Needs attention" },
];

const timeFilters: { key: TimeRange; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "7d", label: "7 days" },
  { key: "30d", label: "30 days" },
];

function statusTone(status: JobStatus): "good" | "bad" {
  if (status === "Failed") {
    return "bad";
  }
  return "good";
}

function compareValues(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") {
    return a - b;
  }
  return String(a).localeCompare(String(b));
}

function sortJobs(items: IngestJob[], key: SortKey, direction: SortDirection): IngestJob[] {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...items].sort((left, right) => {
    let leftValue: string | number = left.id;
    let rightValue: string | number = right.id;

    if (key === "source") {
      leftValue = left.source;
      rightValue = right.source;
    } else if (key === "mode") {
      leftValue = left.mode;
      rightValue = right.mode;
    } else if (key === "status") {
      leftValue = left.status;
      rightValue = right.status;
    } else if (key === "startedAt") {
      leftValue = left.startedAt;
      rightValue = right.startedAt;
    } else if (key === "finishedAt") {
      leftValue = left.finishedAt;
      rightValue = right.finishedAt;
    } else if (key === "docs") {
      leftValue = left.sourceDocuments;
      rightValue = right.sourceDocuments;
    } else if (key === "chunks") {
      leftValue = left.chunks;
      rightValue = right.chunks;
    }

    return compareValues(leftValue, rightValue) * multiplier;
  });
}

function StatusPill({ label, tone }: { label: string; tone: "good" | "bad" }) {
  return <span className={`status-pill status-pill-${tone}`}>{label}</span>;
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

export function AdminIngestJobsMock() {
  const [sortKey, setSortKey] = useState<SortKey>("startedAt");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 4;

  const filteredJobs = useMemo(() => {
    if (timeRange === "today") {
      return jobs.slice(0, 4);
    }
    if (timeRange === "7d") {
      return jobs.slice(0, 6);
    }
    return jobs;
  }, [timeRange]);

  const sortedJobs = useMemo(
    () => sortJobs(filteredJobs, sortKey, sortDirection),
    [filteredJobs, sortKey, sortDirection]
  );

  const totalPages = Math.max(1, Math.ceil(sortedJobs.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * pageSize;
  const visibleJobs = sortedJobs.slice(pageStart, pageStart + pageSize);

  const selectedJob = selectedJobId
    ? sortedJobs.find((job) => job.id === selectedJobId) ?? null
    : null;

  function setTimeRangeAndReset(nextRange: TimeRange) {
    setTimeRange(nextRange);
    setPage(1);
    setSelectedJobId(null);
  }

  function toggleSort(key: SortKey) {
    setSortKey((currentKey) => {
      if (currentKey === key) {
        setSortDirection((currentDirection) => (currentDirection === "asc" ? "desc" : "asc"));
        return currentKey;
      }
      setSortDirection("desc");
      return key;
    });
    setPage(1);
    setSelectedJobId(null);
  }

  function selectPage(nextPage: number) {
    setPage(nextPage);
    setSelectedJobId(null);
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
              A control-room view for ingest activity: what ran, what’s running, and what needs a
              second look.
            </p>
          </div>
          <div className="admin-hero-actions">
            <button type="button">Run full ingest</button>
            <button type="button" className="secondary-action">
              Run partial ingest
            </button>
            <button type="button" className="secondary-action">
              Retry failed job
            </button>
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
          <p>Showing {sortedJobs.length} job(s) in the selected window</p>
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
                  {visibleJobs.map((job) => (
                    <tr
                      key={job.id}
                      className={`upload-table-row${job.id === selectedJob?.id ? " is-selected" : ""}`}
                      onClick={() => setSelectedJobId(job.id)}
                    >
                      <td>
                        <strong>{job.id}</strong>
                      </td>
                      <td>{job.source}</td>
                      <td>{job.mode}</td>
                      <td>
                        <StatusPill label={job.status} tone={statusTone(job.status)} />
                      </td>
                      <td>{job.startedAt}</td>
                      <td>{job.finishedAt}</td>
                      <td>{job.sourceDocuments}</td>
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
              <div className="pagination-controls" aria-label="Job table pagination">
                <button type="button" onClick={() => selectPage(Math.max(1, currentPage - 1))} disabled={currentPage === 1}>
                  Prev
                </button>
                {Array.from({ length: totalPages }, (_, index) => index + 1).map((pageNumber) => (
                  <button
                    key={pageNumber}
                    type="button"
                    className={pageNumber === currentPage ? "is-active" : ""}
                    onClick={() => selectPage(pageNumber)}
                  >
                    {pageNumber}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => selectPage(Math.min(totalPages, currentPage + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                </button>
              </div>
            </div>
          </section>

          {selectedJob ? (
            <>
              <button
                type="button"
                className="ingest-job-backdrop"
                aria-label="Close selected job details"
                onClick={() => setSelectedJobId(null)}
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
                    onClick={() => setSelectedJobId(null)}
                  >
                    Close
                  </button>
                </div>

                <div className="detail-stack">
                  <section className="detail-card detail-card-status">
                    <div className="detail-card-header">
                      <span>{selectedJob.id}</span>
                      <StatusPill label={selectedJob.status} tone={statusTone(selectedJob.status)} />
                    </div>
                    <small>
                      {selectedJob.source} · {selectedJob.mode} · {selectedJob.startedAt}
                    </small>
                  </section>

                  <section className="detail-card">
                    <span>Summary</span>
                    <strong>{selectedJob.summary}</strong>
                    <p>{selectedJob.resultMessage}</p>
                  </section>

                  <section className="detail-card">
                    <span>Inputs</span>
                    <div className="detail-list">
                      <div>
                        <small>Requested paths</small>
                        <strong>
                          {selectedJob.requestedPaths.length ? selectedJob.requestedPaths.join(", ") : "None"}
                        </strong>
                      </div>
                      <div>
                        <small>Uploaded file ids</small>
                        <strong>
                          {selectedJob.uploadedFileIds.length
                            ? selectedJob.uploadedFileIds.join(", ")
                            : "None"}
                        </strong>
                      </div>
                      <div>
                        <small>Task id</small>
                        <strong>{selectedJob.taskId}</strong>
                      </div>
                    </div>
                  </section>

                  <section className="detail-card">
                    <span>Counts</span>
                    <div className="detail-metric-row">
                      <div>
                        <small>Source docs</small>
                        <strong>{selectedJob.sourceDocuments}</strong>
                      </div>
                      <div>
                        <small>Chunks</small>
                        <strong>{selectedJob.chunks}</strong>
                      </div>
                      <div>
                        <small>State</small>
                        <strong>{selectedJob.status}</strong>
                      </div>
                    </div>
                  </section>

                  {selectedJob.errorMessage ? (
                    <section className="detail-card detail-card-danger">
                      <span>Error</span>
                      <p>{selectedJob.errorMessage}</p>
                    </section>
                  ) : null}
                </div>
              </aside>
            </>
          ) : null}
        </section>
      </section>
    </main>
  );
}
