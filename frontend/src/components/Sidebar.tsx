import { NavLink } from "react-router-dom";

const NAV_ITEMS = [{ to: "/", label: "Mosaic Intelligence" }];

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
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <img src="/mosaic-logo.png" alt="Mosaic" style={{ width: 32, height: 32, objectFit: "contain" }} />
        <div>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Mosaic Info Hub</div>
          <div style={{ color: "var(--text-muted)", fontSize: 12 }}>AI adoption intelligence</div>
        </div>
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
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
    </div>
  );
}
