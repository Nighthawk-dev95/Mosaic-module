interface BadgeProps {
  label: string;
  color?: string;
  dot?: boolean;
}

export function Badge({ label, color = "var(--text-secondary)", dot = false }: BadgeProps) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontSize: 11,
        padding: "2px 10px",
        borderRadius: 999,
        border: `1px solid ${color}`,
        color,
        whiteSpace: "nowrap",
      }}
    >
      {dot && <span style={{ width: 6, height: 6, borderRadius: "50%", background: color, flexShrink: 0 }} />}
      {label}
    </span>
  );
}
