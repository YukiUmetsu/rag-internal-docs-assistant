type PaginationControlsProps = {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  ariaLabel: string;
};

function buildPaginationItems(currentPage: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const items: Array<number | "ellipsis"> = [1];
  const leftSibling = Math.max(currentPage - 1, 2);
  const rightSibling = Math.min(currentPage + 1, totalPages - 1);

  if (leftSibling > 2) {
    items.push("ellipsis");
  }

  for (let page = leftSibling; page <= rightSibling; page += 1) {
    items.push(page);
  }

  if (rightSibling < totalPages - 1) {
    items.push("ellipsis");
  }

  items.push(totalPages);
  return items;
}

export function PaginationControls({
  currentPage,
  totalPages,
  onPageChange,
  ariaLabel,
}: PaginationControlsProps) {
  const safeTotalPages = Math.max(1, totalPages);
  const safeCurrentPage = Math.min(Math.max(currentPage, 1), safeTotalPages);
  const items = buildPaginationItems(safeCurrentPage, safeTotalPages);

  return (
    <div className="pagination-controls" aria-label={ariaLabel}>
      <button
        type="button"
        onClick={() => onPageChange(Math.max(1, safeCurrentPage - 1))}
        disabled={safeCurrentPage === 1}
      >
        Prev
      </button>
      {items.map((item, index) =>
        item === "ellipsis" ? (
          <span className="pagination-ellipsis" key={`${ariaLabel}-ellipsis-${index}`}>
            …
          </span>
        ) : (
          <button
            key={item}
            type="button"
            className={item === safeCurrentPage ? "is-active" : ""}
            aria-current={item === safeCurrentPage ? "page" : undefined}
            onClick={() => onPageChange(item)}
          >
            {item}
          </button>
        )
      )}
      <button
        type="button"
        onClick={() => onPageChange(Math.min(safeTotalPages, safeCurrentPage + 1))}
        disabled={safeCurrentPage === safeTotalPages}
      >
        Next
      </button>
    </div>
  );
}
