import { useEffect, useMemo, useState } from "react";

type UploadItem = {
  filename: string;
  size: string;
  checksum: string;
  status: string;
  linkedJob: string;
  uploadedAt: string;
  uploadedMinutesAgo: number;
};

type UploadMetric = {
  label: string;
  value: string;
  detail: string;
};

const uploadMetrics: UploadMetric[] = [
  { label: "Uploads this week", value: "24", detail: "7 Markdown, 17 PDF" },
  { label: "Awaiting ingest", value: "5", detail: "Queued for the next run" },
  { label: "Avg upload size", value: "1.9 MB", detail: "Below limit" },
  { label: "Duplicate checksums", value: "2", detail: "Not yet deduped" },
];

const recentUploads: UploadItem[] = [
  {
    filename: "security-handbook.pdf",
    size: "3.1 MB",
    checksum: "a29f1c9e7f1d",
    status: "Ready",
    linkedJob: "job-44",
    uploadedAt: "9 min ago",
    uploadedMinutesAgo: 9,
  },
  {
    filename: "vpn-reset.md",
    size: "14 KB",
    checksum: "b41ac3d8e3aa",
    status: "Ready",
    linkedJob: "job-44",
    uploadedAt: "15 min ago",
    uploadedMinutesAgo: 15,
  },
  {
    filename: "quarterly-policy-update.pdf",
    size: "1.7 MB",
    checksum: "d79b8f9e1201",
    status: "Queued",
    linkedJob: "job-45",
    uploadedAt: "31 min ago",
    uploadedMinutesAgo: 31,
  },
  {
    filename: "benefits-faq.md",
    size: "22 KB",
    checksum: "f9a30a118bc1",
    status: "Ready",
    linkedJob: "job-45",
    uploadedAt: "45 min ago",
    uploadedMinutesAgo: 45,
  },
  {
    filename: "leave-policy-2026.md",
    size: "26 KB",
    checksum: "4c7e2b3f1a88",
    status: "Ready",
    linkedJob: "job-46",
    uploadedAt: "1 h ago",
    uploadedMinutesAgo: 60,
  },
  {
    filename: "incident-runbook.pdf",
    size: "2.2 MB",
    checksum: "91a5f8d0b4c2",
    status: "Queued",
    linkedJob: "job-46",
    uploadedAt: "1 h ago",
    uploadedMinutesAgo: 75,
  },
  {
    filename: "network-ops.md",
    size: "33 KB",
    checksum: "7f1c2e9a0d6b",
    status: "Ready",
    linkedJob: "job-47",
    uploadedAt: "2 h ago",
    uploadedMinutesAgo: 120,
  },
  {
    filename: "release-notes-q2.pdf",
    size: "4.0 MB",
    checksum: "0ad7b2e1c9f4",
    status: "Ready",
    linkedJob: "job-47",
    uploadedAt: "2 h ago",
    uploadedMinutesAgo: 135,
  },
  {
    filename: "payroll-change.md",
    size: "19 KB",
    checksum: "8e0b1f3d7c6a",
    status: "Queued",
    linkedJob: "job-48",
    uploadedAt: "3 h ago",
    uploadedMinutesAgo: 190,
  },
  {
    filename: "oncall-guide.pdf",
    size: "1.3 MB",
    checksum: "2f8d9c6e1b44",
    status: "Ready",
    linkedJob: "job-48",
    uploadedAt: "4 h ago",
    uploadedMinutesAgo: 240,
  },
];

const fileTypes = [
  { label: "Markdown", value: "18" },
  { label: "PDF", value: "6" },
  { label: "Waiting ingest", value: "5" },
];

const PAGE_SIZE = 5;
const DEFAULT_SORT = { key: "uploadedAt" as SortKey, direction: "desc" as SortDirection };

type SortKey = "filename" | "size" | "status" | "linkedJob" | "uploadedAt";
type SortDirection = "asc" | "desc";

function statusTone(status: string): "good" | "bad" {
  return status === "Queued" ? "bad" : "good";
}

function parseSizeToKb(size: string): number {
  const match = size.match(/^([\d.]+)\s*(KB|MB)$/i);
  if (!match) {
    return 0;
  }

  const value = Number(match[1]);
  const unit = match[2].toUpperCase();
  return unit === "MB" ? value * 1024 : value;
}

function compareValues(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") {
    return a - b;
  }
  return String(a).localeCompare(String(b));
}

function sortUploads(items: UploadItem[], key: SortKey, direction: SortDirection): UploadItem[] {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...items].sort((left, right) => {
    let leftValue: string | number = left.uploadedMinutesAgo;
    let rightValue: string | number = right.uploadedMinutesAgo;

    if (key === "filename") {
      leftValue = left.filename;
      rightValue = right.filename;
    } else if (key === "size") {
      leftValue = parseSizeToKb(left.size);
      rightValue = parseSizeToKb(right.size);
    } else if (key === "status") {
      leftValue = left.status;
      rightValue = right.status;
    } else if (key === "linkedJob") {
      leftValue = left.linkedJob;
      rightValue = right.linkedJob;
    }

    return compareValues(leftValue, rightValue) * multiplier;
  });
}

function sortDirectionLabel(direction: SortDirection): string {
  return direction === "asc" ? "ascending" : "descending";
}

function UploadSortButton({
  active,
  children,
  direction,
  onClick,
}: {
  active: boolean;
  children: string;
  direction: SortDirection;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`upload-sort-button${active ? " is-active" : ""}`}
      onClick={onClick}
      aria-label={`Sort by ${children} ${sortDirectionLabel(direction)}`}
    >
      <span>{children}</span>
      <small>{active ? (direction === "asc" ? "↑" : "↓") : "↕"}</small>
    </button>
  );
}

export function AdminUploadsMock() {
  const [sortKey, setSortKey] = useState<SortKey>(DEFAULT_SORT.key);
  const [sortDirection, setSortDirection] = useState<SortDirection>(DEFAULT_SORT.direction);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [sortKey, sortDirection]);

  const sortedUploads = useMemo(
    () => sortUploads(recentUploads, sortKey, sortDirection),
    [sortKey, sortDirection]
  );

  const totalPages = Math.max(Math.ceil(sortedUploads.length / PAGE_SIZE), 1);
  const currentPage = Math.min(page, totalPages);
  const pageStart = (currentPage - 1) * PAGE_SIZE;
  const pagedUploads = sortedUploads.slice(pageStart, pageStart + PAGE_SIZE);
  const pageEnd = Math.min(pageStart + PAGE_SIZE, sortedUploads.length);

  function toggleSort(key: SortKey) {
    setSortKey((currentKey) => {
      if (currentKey === key) {
        setSortDirection((currentDirection) => (currentDirection === "asc" ? "desc" : "asc"));
        return currentKey;
      }
      setSortDirection(key === "uploadedAt" ? "desc" : "asc");
      return key;
    });
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
          <a href="/admin/uploads" className="nav-link is-active">
            Uploads
          </a>
          <a href="#queue" className="nav-link">
            Queue
          </a>
        </div>
      </nav>

      <section className="admin-layout">
        <header className="admin-hero">
          <div>
            <p className="section-kicker">Uploads</p>
            <h1>Files waiting to be ingested</h1>
            <p className="section-copy">
              A quick place to drop new documents, watch what landed, and see what still needs to be
              processed.
            </p>
          </div>
          <div className="admin-hero-actions">
            <button type="button">Browse files</button>
            <button type="button" className="secondary-action">
              Upload now
            </button>
            <button type="button" className="secondary-action">
              Run ingest
            </button>
          </div>
        </header>

        <section className="upload-primary-row">
          <section className="admin-panel upload-dropzone-panel">
            <div className="admin-panel-header">
              <div>
                <span>Drop files here</span>
                <p>Accepts Markdown and PDF up to 100 MB each</p>
              </div>
            </div>
            <div className="upload-dropzone">
              <div className="upload-dropzone-inner">
                <strong>Drag and drop files</strong>
                <span>or use the browse button to pick local documents</span>
              </div>
              <div className="upload-dropzone-actions">
                <button type="button">Choose files</button>
                <button type="button" className="secondary-action">
                  Paste paths
                </button>
              </div>
            </div>
          </section>
        </section>

        <section className="upload-insights-row">
          <section className="admin-panel upload-summary-panel">
            <div className="admin-panel-header">
              <div>
                <span>Upload summary</span>
                <p>What landed and what still needs attention</p>
              </div>
            </div>
            <div className="metric-grid metric-grid-upload">
              {uploadMetrics.map((metric) => (
                <article className="metric-card metric-card-compact" key={metric.label}>
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                  <small>{metric.detail}</small>
                </article>
              ))}
            </div>
          </section>

          <section className="admin-panel upload-filetypes-panel">
            <div className="admin-panel-header">
              <div>
                <span>File types</span>
                <p>What the upload bucket looks like right now</p>
              </div>
            </div>
            <div className="filetype-list">
              {fileTypes.map((item) => (
                <article className="filetype-row" key={item.label}>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </div>
          </section>
        </section>

        <section className="admin-panel" id="queue">
          <div className="admin-panel-header">
            <div>
              <span>Recent uploads</span>
              <p>Files that were added most recently</p>
            </div>
          </div>
          <div className="table-toolbar">
            <p>
              Showing {pageStart + 1}-{pageEnd} of {sortedUploads.length}
            </p>
            <div className="pagination-controls" aria-label="Upload pages">
              <button
                type="button"
                onClick={() => setPage((currentPageValue) => Math.max(currentPageValue - 1, 1))}
                disabled={currentPage === 1}
              >
                Prev
              </button>
              {Array.from({ length: totalPages }, (_, index) => index + 1).map((pageNumber) => (
                <button
                  key={pageNumber}
                  type="button"
                  className={pageNumber === currentPage ? "is-active" : ""}
                  onClick={() => setPage(pageNumber)}
                >
                  {pageNumber}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setPage((currentPageValue) => Math.min(currentPageValue + 1, totalPages))}
                disabled={currentPage === totalPages}
              >
                Next
              </button>
            </div>
          </div>
          <div className="table-card">
            <table className="upload-table">
              <thead>
                <tr className="upload-table-head">
                  <th>
                    <UploadSortButton
                      active={sortKey === "filename"}
                      direction={sortDirection}
                      onClick={() => toggleSort("filename")}
                    >
                      Filename
                    </UploadSortButton>
                  </th>
                  <th>
                    <UploadSortButton
                      active={sortKey === "size"}
                      direction={sortDirection}
                      onClick={() => toggleSort("size")}
                    >
                      Size
                    </UploadSortButton>
                  </th>
                  <th>
                    <UploadSortButton
                      active={sortKey === "status"}
                      direction={sortDirection}
                      onClick={() => toggleSort("status")}
                    >
                      Status
                    </UploadSortButton>
                  </th>
                  <th>
                    <UploadSortButton
                      active={sortKey === "linkedJob"}
                      direction={sortDirection}
                      onClick={() => toggleSort("linkedJob")}
                    >
                      Job
                    </UploadSortButton>
                  </th>
                  <th>
                    <UploadSortButton
                      active={sortKey === "uploadedAt"}
                      direction={sortDirection}
                      onClick={() => toggleSort("uploadedAt")}
                    >
                      Uploaded
                    </UploadSortButton>
                  </th>
                </tr>
              </thead>
              <tbody>
                {pagedUploads.map((upload) => (
                  <tr key={upload.checksum} className="upload-table-row">
                    <td>
                      <strong>{upload.filename}</strong>
                    </td>
                    <td>{upload.size}</td>
                    <td>
                      <StatusPill label={upload.status} tone={statusTone(upload.status)} />
                    </td>
                    <td>{upload.linkedJob}</td>
                    <td>{upload.uploadedAt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </main>
  );
}

function StatusPill({ label, tone }: { label: string; tone: "good" | "bad" }) {
  return <span className={`status-pill status-pill-${tone}`}>{label}</span>;
}
