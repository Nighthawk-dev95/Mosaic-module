import type { ReactNode } from "react";

export interface DataTableColumn<T> {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
}

function defaultRender(value: unknown): ReactNode {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value);
}

// A row-hover highlight needs a real CSS rule (inline styles can't express :hover) - this is
// the one deliberate exception to the rest of the app's all-inline-styles convention.
const HOVER_STYLE = `.dt-row:hover td { background: var(--surface-raised); }`;

export function DataTable<T>({ columns, rows, rowKey }: DataTableProps<T>) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
      <style>{HOVER_STYLE}</style>
      <thead>
        <tr>
          {columns.map((c) => (
            <th
              key={c.key}
              style={{
                textAlign: "left",
                color: "var(--text-muted)",
                borderBottom: "1px solid var(--gridline)",
                padding: "10px 14px",
                fontWeight: 700,
                whiteSpace: "nowrap",
                position: "sticky",
                top: 0,
                zIndex: 1,
                background: "var(--surface-1)",
              }}
            >
              {c.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={rowKey(row)} className="dt-row">
            {columns.map((c) => (
              <td
                key={c.key}
                style={{
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--gridline)",
                  color: "var(--text-primary)",
                  whiteSpace: "nowrap",
                  transition: "background 0.1s ease",
                }}
              >
                {c.render ? c.render(row) : defaultRender((row as unknown as Record<string, unknown>)[c.key])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function fmtPct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${(value * 100).toFixed(1)}%`;
}
