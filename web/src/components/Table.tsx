import { Fragment, ReactNode, useState } from "react";

export interface Column<T> {
  header: string;
  cell: (row: T) => ReactNode;
}

interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  empty?: string;
  /** When provided, rows become clickable and toggle an expanded detail row. */
  expandedContent?: (row: T) => ReactNode;
  /** Stable key per row (defaults to the row index). */
  rowKey?: (row: T, index: number) => string | number;
}

export function Table<T>({ columns, rows, empty, expandedContent, rowKey }: TableProps<T>) {
  const [open, setOpen] = useState<Set<string | number>>(new Set());
  if (!rows.length) return <div className="empty">{empty ?? "Nothing here yet."}</div>;

  const expandable = !!expandedContent;
  const toggle = (key: string | number) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  return (
    <table className="table">
      <thead>
        <tr>
          {expandable && <th className="caret-col" aria-hidden />}
          {columns.map((c) => (
            <th key={c.header}>{c.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => {
          const key = rowKey ? rowKey(row, i) : i;
          const isOpen = open.has(key);
          return (
            <Fragment key={key}>
              <tr
                className={expandable ? "clickable" : undefined}
                onClick={expandable ? () => toggle(key) : undefined}
              >
                {expandable && (
                  <td className="caret-col">
                    <span className={`caret${isOpen ? " open" : ""}`}>▸</span>
                  </td>
                )}
                {columns.map((c) => (
                  <td key={c.header}>{c.cell(row)}</td>
                ))}
              </tr>
              {expandable && isOpen && (
                <tr className="expanded-row">
                  <td colSpan={columns.length + 1}>{expandedContent!(row)}</td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}
