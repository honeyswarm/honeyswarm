import { ReactNode } from "react";

export interface Column<T> {
  header: string;
  cell: (row: T) => ReactNode;
}

export function Table<T>({ columns, rows, empty }: { columns: Column<T>[]; rows: T[]; empty?: string }) {
  if (!rows.length) return <div className="empty">{empty ?? "Nothing here yet."}</div>;
  return (
    <table className="table">
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.header}>{c.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {columns.map((c) => (
              <td key={c.header}>{c.cell(row)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
