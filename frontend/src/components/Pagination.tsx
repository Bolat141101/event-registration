export function Pagination({
  list,
}: {
  list: {
    data: unknown[] | null;
    offset: number;
    nextOffset: number | null;
    setOffset: (value: number) => void;
  };
}) {
  if (!list.data || (list.offset === 0 && list.nextOffset === null)) return null;
  return (
    <nav className="pagination" aria-label="Event pages">
      <button
        className="secondary"
        disabled={list.offset === 0}
        onClick={() => list.setOffset(Math.max(0, list.offset - 20))}
      >
        Previous
      </button>
      <span>Page {Math.floor(list.offset / 20) + 1}</span>
      <button
        className="secondary"
        disabled={list.nextOffset === null}
        onClick={() => {
          if (list.nextOffset !== null) list.setOffset(list.nextOffset);
        }}
      >
        Next
      </button>
    </nav>
  );
}
