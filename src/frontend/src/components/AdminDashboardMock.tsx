type Metric = {
  label: string;
  value: string;
  detail: string;
};

type SeriesPoint = {
  label: string;
  value: number;
};

type QuestionStat = {
  question: string;
  count: number;
  lastAsked: string;
  avgLatency: string;
};

type JobStat = {
  id: string;
  source: string;
  mode: string;
  status: string;
  summary: string;
  startedAt: string;
};

type UploadStat = {
  filename: string;
  size: string;
  checksum: string;
  job: string;
  createdAt: string;
};

const metrics: Metric[] = [
  { label: "Active documents", value: "128", detail: "+4 from yesterday" },
  { label: "Active chunks", value: "1,842", detail: "Average 14.4 chunks per doc" },
  { label: "Searches this week", value: "316", detail: "Up 18% vs prior week" },
  { label: "Avg retrieval latency", value: "1.8 s", detail: "Postgres + rerank" },
];

const searchVolume: SeriesPoint[] = [
  { label: "Mon", value: 26 },
  { label: "Tue", value: 34 },
  { label: "Wed", value: 31 },
  { label: "Thu", value: 42 },
  { label: "Fri", value: 45 },
  { label: "Sat", value: 18 },
  { label: "Sun", value: 24 },
];

const latencySeries: SeriesPoint[] = [
  { label: "Mon", value: 2.2 },
  { label: "Tue", value: 1.9 },
  { label: "Wed", value: 1.8 },
  { label: "Thu", value: 1.6 },
  { label: "Fri", value: 1.7 },
  { label: "Sat", value: 1.5 },
  { label: "Sun", value: 1.6 },
];

const ingestSeries: SeriesPoint[] = [
  { label: "Mon", value: 2 },
  { label: "Tue", value: 1 },
  { label: "Wed", value: 3 },
  { label: "Thu", value: 2 },
  { label: "Fri", value: 4 },
  { label: "Sat", value: 1 },
  { label: "Sun", value: 2 },
];

const topQuestions: QuestionStat[] = [
  {
    question: "What is the refund window in 2026?",
    count: 18,
    lastAsked: "12 min ago",
    avgLatency: "1.7 s",
  },
  {
    question: "How many PTO days do employees get?",
    count: 11,
    lastAsked: "28 min ago",
    avgLatency: "1.6 s",
  },
  {
    question: "When is manager approval required for refunds?",
    count: 7,
    lastAsked: "1 h ago",
    avgLatency: "2.0 s",
  },
];

const jobs: JobStat[] = [
  {
    id: "job-41",
    source: "mounted_data",
    mode: "full",
    status: "succeeded",
    summary: "3 docs, 41 chunks",
    startedAt: "12 min ago",
  },
  {
    id: "job-40",
    source: "uploaded_files",
    mode: "partial",
    status: "succeeded",
    summary: "1 doc, 8 chunks",
    startedAt: "1 h ago",
  },
  {
    id: "job-39",
    source: "mounted_data",
    mode: "full",
    status: "failed",
    summary: "file parse timeout",
    startedAt: "3 h ago",
  },
];

const uploads: UploadStat[] = [
  {
    filename: "team-handbook.pdf",
    size: "2.4 MB",
    checksum: "a1b2c3d4e5f6",
    job: "job-40",
    createdAt: "1 h ago",
  },
  {
    filename: "policy-update.md",
    size: "18 KB",
    checksum: "c3d4e5f6a7b8",
    job: "job-41",
    createdAt: "12 min ago",
  },
  {
    filename: "engineering-runbook.pdf",
    size: "5.1 MB",
    checksum: "f8e7d6c5b4a3",
    job: "job-41",
    createdAt: "12 min ago",
  },
];

const healthFlags = [
  { label: "Orphan chunks", value: "0" },
  { label: "Docs without chunks", value: "0" },
  { label: "Missing uploads", value: "0" },
  { label: "Failed jobs", value: "1" },
];

function maxValue(series: SeriesPoint[]): number {
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
  series: SeriesPoint[];
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
        {series.map((point) => (
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
            <strong>{point.label}</strong>
            <small>
              {point.value}
              {unit}
            </small>
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusPill({ label, tone }: { label: string; tone: string }) {
  return <span className={`status-pill status-pill-${tone}`}>{label}</span>;
}

export function AdminDashboardMock() {
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
          <a href="#uploads" className="nav-link">
            Uploads
          </a>
          <a href="#jobs" className="nav-link">
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
            <button type="button">Switch retriever</button>
            <button type="button" className="secondary-action">
              Run ingest
            </button>
            <button type="button" className="secondary-action">
              Upload files
            </button>
          </div>
        </header>

        <section className="admin-status-strip" aria-label="System status">
          <div>
            <span className="status-label">Active retriever</span>
            <strong>Postgres</strong>
          </div>
          <div className="admin-status-card admin-status-card-emphasis">
            <span className="status-label">Corpus status</span>
            <div className="status-card-value">
              <strong>Healthy</strong>
              <small>Integrity checks passing</small>
            </div>
          </div>
          <div>
            <span className="status-label">Last ingest</span>
            <strong>12 minutes ago</strong>
          </div>
          <div>
            <span className="status-label">Latest query</span>
            <strong>Refund window in 2026</strong>
          </div>
        </section>

        <section className="metric-grid" aria-label="Summary stats">
          {metrics.map((metric) => (
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
            series={searchVolume}
            unit=""
          />
          <DashboardChart
            title="Retrieval latency"
            subtitle="Average retrieval latency by day"
            series={latencySeries}
            unit=" s"
          />
          <DashboardChart
            title="Ingest jobs"
            subtitle="Completed jobs by day"
            series={ingestSeries}
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
              {topQuestions.map((question, index) => (
                <article className="question-row" key={question.question}>
                  <div className="question-rank">{index + 1}</div>
                  <div className="question-body">
                    <strong>{question.question}</strong>
                    <span>
                      {question.count} asks this week · last asked {question.lastAsked} · avg{" "}
                      {question.avgLatency}
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
              {[
                ["What is the refund window in 2026?", "46"],
                ["How many PTO days do employees get?", "29"],
                ["When is manager approval required for refunds?", "21"],
                ["How do I reset my VPN token?", "14"],
              ].map(([label, value]) => (
                <div className="month-row" key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
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
              {jobs.map((job) => (
                <article className="table-row" key={job.id}>
                  <div className="table-row-topline">
                    <strong>{job.id}</strong>
                    <StatusPill
                      label={job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                      tone={job.status === "failed" ? "bad" : "good"}
                    />
                  </div>
                  <div className="table-row-details">
                    <span>{job.source}</span>
                    <span>{job.mode}</span>
                    <span>{job.startedAt}</span>
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
              {healthFlags.map((flag) => (
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
              {uploads.map((upload) => (
                <article className="table-row" key={upload.checksum}>
                  <div className="table-row-topline">
                    <strong>{upload.filename}</strong>
                    <small>{upload.size}</small>
                  </div>
                  <div className="table-row-details">
                    <small>{upload.checksum}</small>
                    <small>job {upload.job}</small>
                    <small>{upload.createdAt}</small>
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
                <strong>128</strong>
              </div>
              <div>
                <span>Active chunks</span>
                <strong>1,842</strong>
              </div>
              <div>
                <span>Searches today</span>
                <strong>52</strong>
              </div>
              <div>
                <span>Avg answer latency</span>
                <strong>2.4 s</strong>
              </div>
            </div>
          </section>
        </section>
      </section>
    </main>
  );
}
