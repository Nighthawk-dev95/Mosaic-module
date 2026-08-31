interface StatTileProps {
  label: string;
  value: string;
  sublabel?: string;
}

export function StatTile({ label, value, sublabel }: StatTileProps) {
  return (
    <div
      style={{
        background: "var(--surface-1)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: "16px 20px",
        flex: "1 1 200px",
        minWidth: 180,
      }}
    >
      <div style={{ color: "var(--text-muted)", fontSize: 13 }}>{label}</div>
      <div style={{ color: "var(--text-primary)", fontSize: 32, fontWeight: 600, marginTop: 4 }}>
        {value}
      </div>
      {sublabel && (
        <div style={{ color: "var(--success-text)", fontSize: 13, marginTop: 4 }}>{sublabel}</div>
      )}
    </div>
  );
}
