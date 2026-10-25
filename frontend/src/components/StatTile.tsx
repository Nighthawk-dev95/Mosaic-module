import { Line, LineChart, ResponsiveContainer } from "recharts";

interface StatTileProps {
  label: string;
  value: string;
  sublabel?: string;
  accent?: string;
  trend?: number[];
  // Click-to-drill-down / click-to-filter (MVP Overview/Mammo/Weekly Report impact tiles,
  // All Radiologists' Priority/Cohort tiles). `active` highlights the tile currently driving a
  // filter; `disabled` renders it visibly inert (e.g. Weekly Report's past-week tiles, where
  // per-radiologist drill-down genuinely isn't available) rather than silently doing nothing.
  onClick?: () => void;
  active?: boolean;
  disabled?: boolean;
  title?: string;
}

export function StatTile({ label, value, sublabel, accent, trend, onClick, active, disabled, title }: StatTileProps) {
  return (
    <div
      className="mosaic-card-hover"
      onClick={disabled ? undefined : onClick}
      title={title}
      style={{
        background: "var(--glass-fill-card)",
        backdropFilter: "blur(var(--glass-blur-md))",
        WebkitBackdropFilter: "blur(var(--glass-blur-md))",
        border: active ? "1px solid var(--rp-moss, var(--domain-deployment))" : "var(--glass-border)",
        borderLeft: accent ? `3px solid ${accent}` : "var(--glass-border)",
        boxShadow: "var(--glass-shadow-card), var(--glass-highlight)",
        borderRadius: "var(--radius-lg)",
        padding: "16px 20px",
        flex: "1 1 200px",
        minWidth: 180,
        display: "flex",
        flexDirection: "column",
        gap: 4,
        cursor: onClick && !disabled ? "pointer" : undefined,
        opacity: disabled ? 0.5 : 1,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div>
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>{label}</div>
          <div style={{ color: "var(--text-primary)", fontSize: 32, fontWeight: 600, marginTop: 4 }}>{value}</div>
          {sublabel && <div style={{ color: "var(--success-text)", fontSize: 13, marginTop: 4 }}>{sublabel}</div>}
        </div>
        {trend && trend.length > 1 && (
          <div style={{ width: 64, height: 28, flexShrink: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend.map((v, i) => ({ i, v }))}>
                <Line
                  type="monotone"
                  dataKey="v"
                  stroke={accent ?? "var(--text-secondary)"}
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
