import type { ReactNode } from "react";

type Props = {
  text: string;
};

type TableRow = string[];

export function MarkdownPreview({ text }: Props) {
  const blocks = parseMarkdownBlocks(text);
  return (
    <div className="markdown-preview">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return <h4 key={index}>{renderInline(block.text)}</h4>;
        }
        if (block.type === "ul") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        }
        if (block.type === "ol") {
          return (
            <ol key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item)}</li>
              ))}
            </ol>
          );
        }
        if (block.type === "table") {
          const [header, ...rows] = block.rows;
          return (
            <div className="markdown-table-wrap" key={index}>
              <table>
                <thead>
                  <tr>
                    {header.map((cell, cellIndex) => (
                      <th key={cellIndex}>{renderInline(cell)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((cell, cellIndex) => (
                        <td key={cellIndex}>{renderInline(cell)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        return <p key={index}>{renderInline(block.text)}</p>;
      })}
    </div>
  );
}

type Block =
  | { type: "heading"; text: string }
  | { type: "p"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "table"; rows: TableRow[] };

function parseMarkdownBlocks(text: string): Block[] {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    const heading = line.match(/^#{1,6}\s+(.+)$/);
    if (heading) {
      blocks.push({ type: "heading", text: heading[1] });
      index += 1;
      continue;
    }

    if (isBulletLine(line)) {
      const items: string[] = [];
      while (index < lines.length && isBulletLine(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*]\s+/, ""));
        index += 1;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    if (isNumberedLine(line)) {
      const items: string[] = [];
      while (index < lines.length && isNumberedLine(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    if (isTableLine(line)) {
      const rows: TableRow[] = [];
      while (index < lines.length && isTableLine(lines[index].trim())) {
        const rowLine = lines[index].trim();
        if (!isTableDivider(rowLine)) {
          rows.push(parseTableRow(rowLine));
        }
        index += 1;
      }
      if (rows.length >= 2) {
        blocks.push({ type: "table", rows });
      } else {
        blocks.push({ type: "p", text: rows.flat().join(" ") });
      }
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length && shouldContinueParagraph(lines[index].trim())) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "p", text: paragraph.join(" ") });
  }

  return blocks;
}

function shouldContinueParagraph(line: string): boolean {
  return Boolean(
    line &&
      !line.match(/^#{1,6}\s+/) &&
      !isBulletLine(line) &&
      !isNumberedLine(line) &&
      !isTableLine(line)
  );
}

function isBulletLine(line: string): boolean {
  return /^[-*]\s+/.test(line);
}

function isNumberedLine(line: string): boolean {
  return /^\d+\.\s+/.test(line);
}

function isTableLine(line: string): boolean {
  return line.includes("|") && line.split("|").length >= 3;
}

function isTableDivider(line: string): boolean {
  return /^[\s|:-]+$/.test(line);
}

function parseTableRow(line: string): TableRow {
  return line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}
