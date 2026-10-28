import { NavLink } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";

const NAV_ITEMS = [
  { to: "/", label: "Mosaic" },
  { to: "/draft-vs-final", label: "Draft vs Final" },
];

export function Sidebar() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div
      style={{
        width: 220,
        // A width alone does not hold here. This is a flex item next to a surface that can
        // overflow sideways (Explore's grid, Command's chain), and the browser's first move
        // when it needs room is to shrink the sibling that said it could - which squeezed the
        // brand down to about 75px and broke "Mosaic Intelligence" across three lines.
        flexShrink: 0,
        background: "var(--glass-fill-drawer)",
        backdropFilter: "blur(var(--glass-blur-md))",
        WebkitBackdropFilter: "blur(var(--glass-blur-md))",
        border: "var(--glass-border)",
        boxShadow: "var(--glass-shadow-modal), var(--glass-highlight)",
        borderRadius: 0,
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
          <div style={{ fontWeight: "var(--font-weight-bold)", fontSize: "var(--font-size-15)" }}>Mosaic Intelligence</div>
          <div style={{ color: "var(--text-muted)", fontSize: "var(--font-size-12)" }}>Practice Command Centre</div>
        </div>
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className="mosaic-nav-link"
            style={({ isActive }) => ({
              padding: "8px 10px",
              borderRadius: "var(--radius)",
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              background: isActive ? "var(--surface-raised)" : "transparent",
              textDecoration: "none",
              fontSize: "var(--font-size-14)",
              transition: `background var(--dur-card) var(--ease-standard)`,
            })}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <button
        onClick={toggleTheme}
        style={{
          marginTop: "auto",
          padding: "8px 10px",
          borderRadius: "var(--radius)",
          border: "var(--glass-border)",
          background: "var(--surface-raised)",
          color: "var(--text-secondary)",
          fontSize: "var(--font-size-13)",
          cursor: "pointer",
          transition: `background var(--dur-card) var(--ease-standard)`,
        }}
      >
        {theme === "dark" ? "☀ Light mode" : "☾ Dark mode"}
      </button>
    </div>
  );
}
