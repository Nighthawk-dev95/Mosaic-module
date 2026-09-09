interface TrendDeltaProps {
  value: number | null | undefined;
}

export function TrendDelta({ value }: TrendDeltaProps) {
  if (value === null || value === undefined) {
    return <span style={{ color: "var(--text-muted)" }}>—</span>;
  }
  const color = value > 0 ? "var(--status-good)" : value < 0 ? "var(--status-critical)" : "var(--text-secondary)";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "—";
  return (
    <span style={{ color, fontWeight: 600 }}>
      {arrow} {(Math.abs(value) * 100).toFixed(1)}%
    </span>
  );
}
