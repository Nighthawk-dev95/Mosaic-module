import { useState } from "react";
import { MvpOverview } from "./mvp/MvpOverview";
import { MvpMentorship } from "./mvp/MvpMentorship";
import { MvpMammo } from "./mvp/MvpMammo";
import { MvpAreaDetail } from "./mvp/MvpAreaDetail";
import { MvpAllRadiologists } from "./mvp/MvpAllRadiologists";
import { MvpWeeklyReport } from "./mvp/MvpWeeklyReport";

type MvpTab = "overview" | "mentorship" | "mammo" | "area" | "all" | "weekly-report";

const TABS: { key: MvpTab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "mentorship", label: "Mentorship" },
  { key: "mammo", label: "Mammo Screening" },
  { key: "area", label: "Area Detail" },
  { key: "all", label: "All Radiologists" },
  { key: "weekly-report", label: "Weekly Report" },
];

// Rebuilt to mirror the real MVP Weekly Update report sent to C-suite leadership every Friday
// (see declarative-dancing-willow.md plan, "MVP module rebuild") - 5 sub-tabs instead of one
// flat table, same interaction pattern as Capacity's existing "By Practice/By Radiologist"
// toggle.
export function Mvp() {
  const [tab, setTab] = useState<MvpTab>("overview");

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20, flex: 1, minHeight: 0, overflowY: "auto" }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 20 }}>MVP - Mosaic Value Project</h1>
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
          Read directly from the program's own Dynamics-synced tracker and working files - cohort, status, efficiency-change, and
          mentor-matching figures are the real program's own numbers.
        </div>
      </div>

      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border)" }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              background: "transparent",
              border: "none",
              borderBottom: tab === t.key ? "2px solid var(--rp-moss, var(--domain-deployment))" : "2px solid transparent",
              color: tab === t.key ? "var(--text-primary)" : "var(--text-secondary)",
              fontWeight: tab === t.key ? 600 : 400,
              cursor: "pointer",
              padding: "8px 14px",
              fontSize: 13,
              transition: "color var(--dur-card) var(--ease-standard)",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <MvpOverview />}
      {tab === "mentorship" && <MvpMentorship />}
      {tab === "mammo" && <MvpMammo />}
      {tab === "area" && <MvpAreaDetail />}
      {tab === "all" && <MvpAllRadiologists />}
      {tab === "weekly-report" && <MvpWeeklyReport />}
    </div>
  );
}
