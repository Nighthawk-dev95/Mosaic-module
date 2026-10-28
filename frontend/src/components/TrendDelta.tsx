interface TrendDeltaProps {
  value: number | null | undefined;
  /**
   * How to read `value`. "pct" is a relative change (0.05 = +5% of the base); "pp" is an
   * absolute change between two rates (0.05 = +5.0 points) and renders as "pts".
   *
   * The distinction is not cosmetic. A relative change in a rate rendered with a bare "%"
   * is read as points by every human who looks at it - that is the same mistake that put
   * a "+6536.8%" on the Cockpit worklist, and the same one that made a +0.83pp move
   * outrank a +37pp move on the Capture page. Default stays "pct" so existing call sites
   * (e.g. the "Delta Since Enablement" column) are unchanged.
   */
  unit?: "pct" | "pp";
}

export function TrendDelta({ value, unit = "pct" }: TrendDeltaProps) {
  if (value === null || value === undefined) {
    return <span style={{ color: "var(--text-muted)" }}>—</span>;
  }
  const color = value > 0 ? "var(--status-good)" : value < 0 ? "var(--status-critical)" : "var(--text-secondary)";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "—";
  const magnitude = (Math.abs(value) * 100).toFixed(1);
  return (
    <span style={{ color, fontWeight: 600 }}>
      {arrow} {magnitude}
      {unit === "pp" ? " pts" : "%"}
    </span>
  );
}
