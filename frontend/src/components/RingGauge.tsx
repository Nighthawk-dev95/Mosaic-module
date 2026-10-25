import { useEffect, useState } from "react";

// Animated circular gauge (progress ring) - value sweeps in from 0 on mount/value change rather
// than snapping to its final position, so a changed value reads as the dashboard "recomputing"
// instead of silently swapping a static image. Originally built for BaselineReviewQueue's match
// scores; reused as-is by MosaicPulse for adoption percentages via the `format` option.
export function RingGauge({
  value,
  max,
  size,
  strokeWidth,
  color,
  delayMs = 0,
  label,
  replayTrigger = 0,
  format,
}: {
  value: number | null;
  max: number;
  size: number;
  strokeWidth: number;
  color: string;
  delayMs?: number;
  label?: string;
  replayTrigger?: number;
  /** Renders the center text - defaults to the raw value. Pass e.g. `(v) => `${v.toFixed(0)}%`` */
  format?: (value: number) => string;
}) {
  const targetPct = value === null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  const [pct, setPct] = useState(0);

  // replayTrigger changes on an external cue (e.g. hover, or a data refresh) even though
  // value/max don't - that's the point, it's how a gauge already at its final position re-sweeps.
  useEffect(() => {
    setPct(0);
    const t = setTimeout(() => setPct(targetPct), 30 + delayMs);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetPct, delayMs, value, replayTrigger]);

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct / 100);
  const center = size / 2;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={size} height={size}>
        <g transform={`rotate(-90 ${center} ${center})`}>
          <circle cx={center} cy={center} r={radius} fill="none" stroke="var(--surface-raised)" strokeWidth={strokeWidth} />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset var(--dur-kpi) var(--ease-spring)" }}
          />
        </g>
        <text
          x={center}
          y={center}
          textAnchor="middle"
          dominantBaseline="central"
          style={{ fontSize: size * 0.3, fontWeight: 700, fill: "var(--text-primary)" }}
        >
          {value === null ? "—" : format ? format(value) : value}
        </text>
      </svg>
      {label && <div style={{ fontSize: 10, color: "var(--text-muted)", textAlign: "center", lineHeight: 1.2 }}>{label}</div>}
    </div>
  );
}
