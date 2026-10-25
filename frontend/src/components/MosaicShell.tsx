import { NavLink, Outlet } from "react-router-dom";
import { RefreshStatus } from "./RefreshStatus";
import { CacheWarmupBanner } from "./CacheWarmupBanner";
import { TimeOfDayGreeting } from "./TimeOfDayGreeting";
import { GenieAskPanel } from "./GenieAskPanel";
import { TABS } from "../utils/tabs";

// Persistent chrome (title, data-freshness badge, tab bar) around whichever tab's page is
// currently routed - every tab is a real nested route (so URLs stay deep-linkable/shareable),
// this component just supplies the header/tab bar that wraps the <Outlet/>.
export function MosaicShell() {
  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <div style={{ padding: "20px 24px 0", display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <TimeOfDayGreeting />
            <div>
              <h1 style={{ margin: 0, fontSize: 22 }}>Mosaic Intelligence</h1>
              <div style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 2 }}>
                Enterprise-wide Mosaic AI adoption, deployment, efficiency, capacity, and capture intelligence.
              </div>
            </div>
          </div>
          <RefreshStatus />
        </div>

        <nav style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border)" }}>
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className="mosaic-nav-tab"
              style={({ isActive }) => ({
                padding: "10px 16px",
                fontSize: 13,
                fontWeight: 600,
                textDecoration: "none",
                color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                borderBottom: isActive ? "2px solid var(--color-primary)" : "2px solid transparent",
                marginBottom: -1,
                transition: `color var(--dur-card) var(--ease-standard), border-color var(--dur-card) var(--ease-standard)`,
              })}
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </div>

      <CacheWarmupBanner />

      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        <Outlet />
      </div>

      <GenieAskPanel />
    </div>
  );
}
