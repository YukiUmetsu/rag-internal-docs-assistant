import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { listAdminUploads, uploadAdminFiles } from "../api/admin";
import { PaginationControls } from "./PaginationControls";
import type {
  AdminUploadSortKey,
  AdminUploadStat,
  SortDirection,
} from "../api/types";

type UploadMetric = {
  label: string;
  value: string;
  detail: string;
};

const PAGE_SIZE = 5;
const DEFAULT_SORT = { key: "created_at" as AdminUploadSortKey, direction: "desc" as SortDirection };

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

function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (bytes >= 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${bytes} B`;
}

function inferFileType(filename: string): "Markdown" | "PDF" | "Other" {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".md")) {
    return "Markdown";
  }
  if (lower.endsWith(".pdf")) {
    return "PDF";
  }
  return "Other";
}

function compareValues(a: string | number, b: string | number): number {
  if (typeof a === "number" && typeof b === "number") {
    return a - b;
  }
  return String(a).localeCompare(String(b));
}

function isSupportedUploadFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".md") || name.endsWith(".pdf");
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
      aria-label={`Sort by ${children}`}
    >
      <span>{children}</span>
      <small>{active ? (direction === "asc" ? "↑" : "↓") : "↕"}</small>
    </button>
  );
}

function sortUploads(items: AdminUploadStat[], key: AdminUploadSortKey, direction: SortDirection): AdminUploadStat[] {
  const multiplier = direction === "asc" ? 1 : -1;
  return [...items].sort((left, right) => {
    let leftValue: string | number = left.created_at;
    let rightValue: string | number = right.created_at;

    if (key === "filename") {
      leftValue = left.filename;
      rightValue = right.filename;
    } else if (key === "size") {
      leftValue = left.size_bytes;
      rightValue = right.size_bytes;
    } else if (key === "checksum") {
      leftValue = left.checksum;
      rightValue = right.checksum;
    } else if (key === "job_id") {
      leftValue = left.job_id ?? "";
      rightValue = right.job_id ?? "";
    }

    return compareValues(leftValue, rightValue) * multiplier;
  });
}

export function AdminUploads() {
  const [uploads, setUploads] = useState<AdminUploadStat[]>([]);
  const [total, setTotal] = useState(0);
  const [sortKey, setSortKey] = useState<AdminUploadSortKey>(DEFAULT_SORT.key);
  const [sortDirection, setSortDirection] = useState<SortDirection>(DEFAULT_SORT.direction);
  const [page, setPage] = useState(1);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function loadUploads(nextPage = page, nextSortKey = sortKey, nextSortDirection = sortDirection) {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listAdminUploads({
        limit: PAGE_SIZE,
        offset: (nextPage - 1) * PAGE_SIZE,
        sortBy: nextSortKey,
        sortDir: nextSortDirection,
      });
      setUploads(response.items);
      setTotal(response.total);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load uploads.");
      setUploads([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }

  function focusFilePicker() {
    fileInputRef.current?.click();
  }

  function resetSelection({ preserveStatus = false }: { preserveStatus?: boolean } = {}) {
    setSelectedFiles([]);
    if (!preserveStatus) {
      setUploadStatus(null);
    }
    setUploadError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function normalizeSelectedFiles(files: File[]): File[] {
    const supported = files.filter(isSupportedUploadFile);
    const rejected = files.filter((file) => !isSupportedUploadFile(file));
    if (rejected.length) {
      setUploadError(`Ignored unsupported files: ${rejected.map((file) => file.name).join(", ")}`);
    } else {
      setUploadError(null);
    }
    return supported;
  }

  function handleFileSelection(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    setUploadStatus(null);
    setSelectedFiles(normalizeSelectedFiles(files));
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    setUploadStatus(null);
    const files = Array.from(event.dataTransfer.files);
    setSelectedFiles(normalizeSelectedFiles(files));
  }

  async function handleUploadSelectedFiles() {
    if (!selectedFiles.length || isUploading) {
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    setUploadStatus(null);
    try {
      const uploaded = await uploadAdminFiles(selectedFiles);
      resetSelection({ preserveStatus: true });
      setPage(1);
      await loadUploads(1, sortKey, sortDirection);
      setUploadStatus(`Uploaded ${uploaded.length} file${uploaded.length === 1 ? "" : "s"}.`);
    } catch (exc) {
      setUploadError(exc instanceof Error ? exc.message : "Failed to upload files.");
    } finally {
      setIsUploading(false);
    }
  }

  useEffect(() => {
    void loadUploads(page, sortKey, sortDirection);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, sortKey, sortDirection]);

  const sortedPageUploads = useMemo(
    () => sortUploads(uploads, sortKey, sortDirection),
    [uploads, sortKey, sortDirection]
  );

  const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1);
  const currentPage = Math.min(page, totalPages);
  const pageStart = total === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const pageEnd = Math.min(currentPage * PAGE_SIZE, total);
  const pageSize = sortedPageUploads.length;
  const totalBytes = sortedPageUploads.reduce((sum, upload) => sum + upload.size_bytes, 0);
  const markdownCount = sortedPageUploads.filter((upload) => inferFileType(upload.filename) === "Markdown").length;
  const pdfCount = sortedPageUploads.filter((upload) => inferFileType(upload.filename) === "PDF").length;

  const uploadMetrics: UploadMetric[] = [
    { label: "Uploads loaded", value: String(pageSize), detail: `Page ${currentPage} of ${totalPages}` },
    { label: "Uploads total", value: String(total), detail: "Across all pages" },
    { label: "Markdown on page", value: String(markdownCount), detail: "MD files in view" },
    { label: "PDF on page", value: String(pdfCount), detail: "PDF files in view" },
  ];

  function toggleSort(key: AdminUploadSortKey) {
    setPage(1);
    setSortKey((currentKey) => {
      if (currentKey === key) {
        setSortDirection((currentDirection) => (currentDirection === "asc" ? "desc" : "asc"));
        return currentKey;
      }
      setSortDirection(key === "created_at" ? "desc" : "asc");
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
          <a href="/admin/feedback" className="nav-link">
            Feedback
          </a>
          <a href="/admin/uploads" className="nav-link is-active">
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
            <p className="section-kicker">Uploads</p>
            <h1>Files waiting to be ingested</h1>
            <p className="section-copy">
              A quick place to drop new documents, watch what landed, and see what still needs to be
              processed.
            </p>
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
            <input
              ref={fileInputRef}
              type="file"
              accept=".md,.pdf"
              multiple
              className="upload-file-input"
              onChange={handleFileSelection}
            />
            <div
              className={`upload-dropzone${isDragging ? " is-dragging" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragEnter={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
            >
              <div className="upload-dropzone-inner">
                <strong>Drag and drop files</strong>
                <span>or choose files from your computer</span>
              </div>
              <div className="upload-dropzone-files" aria-live="polite">
                {selectedFiles.length ? (
                  <>
                    <span className="upload-dropzone-note">
                      {selectedFiles.length} file{selectedFiles.length === 1 ? "" : "s"} selected
                    </span>
                    <ul>
                      {selectedFiles.map((file) => (
                        <li key={`${file.name}-${file.size}`}>
                          <strong>{file.name}</strong>
                          <span>{formatFileSize(file.size)}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="upload-dropzone-note">
                    Uploaded files appear in the table below once they land.
                  </p>
                )}
              </div>
              {uploadStatus ? <p className="upload-dropzone-success">{uploadStatus}</p> : null}
              {uploadError ? <p className="upload-dropzone-error">{uploadError}</p> : null}
              <div className="upload-dropzone-actions">
                <button type="button" onClick={focusFilePicker} disabled={isUploading}>
                  Choose files
                </button>
                <button
                  type="button"
                  className="secondary-action"
                  onClick={handleUploadSelectedFiles}
                  disabled={!selectedFiles.length || isUploading}
                >
                  {isUploading ? "Uploading..." : "Upload selected"}
                </button>
                <button
                  type="button"
                  className="secondary-action"
                  onClick={() => resetSelection()}
                  disabled={!selectedFiles.length || isUploading}
                >
                  Clear
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
              {[
                { label: "Markdown", value: markdownCount.toString() },
                { label: "PDF", value: pdfCount.toString() },
                { label: "Current page size", value: formatFileSize(totalBytes) },
              ].map((item) => (
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
              Showing {pageStart}-{pageEnd} of {total}
            </p>
            <PaginationControls
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setPage}
              ariaLabel="Upload pages"
            />
          </div>

          {isLoading ? <div className="empty-state">Loading uploads…</div> : null}
          {error ? <div className="empty-state">{error}</div> : null}

          {!isLoading && !error ? (
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
                        active={sortKey === "checksum"}
                        direction={sortDirection}
                        onClick={() => toggleSort("checksum")}
                      >
                        Checksum
                      </UploadSortButton>
                    </th>
                    <th>
                      <UploadSortButton
                        active={sortKey === "job_id"}
                        direction={sortDirection}
                        onClick={() => toggleSort("job_id")}
                      >
                        Job
                      </UploadSortButton>
                    </th>
                    <th>
                      <UploadSortButton
                        active={sortKey === "created_at"}
                        direction={sortDirection}
                        onClick={() => toggleSort("created_at")}
                      >
                        Uploaded
                      </UploadSortButton>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sortedPageUploads.map((upload) => (
                    <tr key={upload.id} className="upload-table-row">
                      <td>
                        <strong>{upload.filename}</strong>
                      </td>
                      <td>{formatFileSize(upload.size_bytes)}</td>
                      <td>{upload.checksum}</td>
                      <td>{upload.job_id ?? "pending"}</td>
                      <td>{formatRelativeTime(upload.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      </section>
    </main>
  );
}
