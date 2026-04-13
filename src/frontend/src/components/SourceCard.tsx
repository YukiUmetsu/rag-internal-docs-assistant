import type { Source } from "../api/types";
import { MarkdownPreview } from "./MarkdownPreview";

type Props = {
  source: Source;
};

export function SourceCard({ source }: Props) {
  const isMarkdown = source.file_name.toLowerCase().endsWith(".md");

  return (
    <article className="source-card">
      <div className="source-card-top">
        <strong>Document {source.rank}</strong>
        {source.year ? <span>{source.year}</span> : null}
      </div>
      <h3>{source.file_name}</h3>
      <dl>
        <div>
          <dt>Domain</dt>
          <dd>{source.domain ?? "unknown"}</dd>
        </div>
        <div>
          <dt>Topic</dt>
          <dd>{source.topic ?? "unknown"}</dd>
        </div>
        {source.page ? (
          <div>
            <dt>Page</dt>
            <dd>{source.page}</dd>
          </div>
        ) : null}
      </dl>
      {isMarkdown ? (
        <MarkdownPreview text={source.preview} />
      ) : (
        <pre className="plain-preview">{source.preview}</pre>
      )}
    </article>
  );
}
