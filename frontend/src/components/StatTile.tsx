import { Line, LineChart, ResponsiveContainer } from "recharts";

interface StatTileProps {
  label: string;
  value: string;
  sublabel?: string;
  accent?: string;
  trend?: number[];
}

export function StatTile({ label, value, sublabel, accent, trend }: StatTileProps) {
  return (
    <div
      className="mosaic-card-hover"
      style={{
        background: "var(--glass-fill-card)",
        backdropFilter: "blur(var(--glass-blur-md))",
        WebkitBackdropFilter: "blur(var(--glass-blur-md))",
        border: "var(--glass-border)",
        borderLeft: accent ? `3px solid ${accent}` : "var(--glass-border)",
        boxShadow: "var(--glass-shadow-card), var(--glass-highlight)",
        borderRadius: "var(--radius-lg)",
        padding: "16px 20px",
        flex: "1 1 200px",
        minWidth: 180,
        display: "flex",
        flexDirection: "column",
        gap: 4,
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
