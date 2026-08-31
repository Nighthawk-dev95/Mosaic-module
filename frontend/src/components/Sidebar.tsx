import { NavLink } from "react-router-dom";
import { RefreshStatus } from "./RefreshStatus";

const NAV_ITEMS = [
  { to: "/", label: "Mosaic Intelligence" },
  { to: "/roster", label: "Radiologist Roster" },
];

const DATA_MODELS: { label: string; color: string; to: string | null }[] = [
  { label: "Deployment", color: "var(--domain-deployment)", to: "/deployment" },
  { label: "Utilization", color: "var(--domain-utilization)", to: "/" },
  { label: "Efficiency", color: "var(--domain-efficiency)", to: "/efficiency" },
  { label: "Capacity", color: "var(--domain-capacity)", to: "/capacity" },
  { label: "Feedback", color: "var(--domain-feedback)", to: null },
];

export function Sidebar() {
  return (
    <div
      style={{
        width: 220,
        background: "var(--surface-1)",
        borderRight: "1px solid var(--border)",
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 24,
        height: "100vh",
        boxSizing: "border-box",
      }}
    >
      <div>
        <div style={{ fontWeight: 700, fontSize: 15 }}>Mosaic Info Hub</div>
        <div style={{ color: "var(--text-muted)", fontSize: 12 }}>AI adoption intelligence</div>
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            style={({ isActive }) => ({
              padding: "8px 10px",
              borderRadius: 6,
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              background: isActive ? "var(--surface-raised)" : "transparent",
              textDecoration: "none",
              fontSize: 14,
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 8, textTransform: "uppercase", letterSpacing: 0.5 }}>
          Data Models
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {DATA_MODELS.map((m) =>
            m.to ? (
              <NavLink
                key={m.label}
                to={m.to}
                style={({ isActive }) => ({
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 13,
                  padding: "6px 10px",
                  borderRadius: 6,
                  textDecoration: "none",
                  color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                  background: isActive ? "var(--surface-raised)" : "transparent",
                })}
              >
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: m.color, flexShrink: 0 }} />
                {m.label}
              </NavLink>
            ) : (
              <div
                key={m.label}
                title="Pending EDW sync - no data available yet"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 13,
                  padding: "6px 10px",
                  color: "var(--text-muted)",
                  cursor: "not-allowed",
                }}
              >
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: m.color, flexShrink: 0, opacity: 0.4 }} />
                {m.label}
                <span style={{ fontSize: 11, marginLeft: "auto" }}>soon</span>
              </div>
            )
          )}
        </div>
      </div>

      <div style={{ marginTop: "auto", paddingTop: 16, borderTop: "1px solid var(--border)" }}>
        <RefreshStatus />
      </div>
    </div>
  );
}
