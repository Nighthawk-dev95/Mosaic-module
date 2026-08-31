import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";

const COLUMNS: { key: string; label: string }[] = [
  { key: "radiologist_name", label: "Radiologist" },
  { key: "home_practice", label: "Practice" },
  { key: "working_subspecialty", label: "Subspecialty" },
  { key: "deployment_status", label: "Deployment Status" },
  { key: "current_team", label: "Team" },
  { key: "reporting_cases_read", label: "Exams Read" },
  { key: "total_drafting_cases", label: "Drafting Cases" },
];

export function RadiologistRoster() {
  const roster = useFetch(() => mosaicApi.getRoster({ limit: 100 }), []);

  return (
    <div style={{ padding: 24, flex: 1, overflowY: "auto" }}>
      <h1 style={{ margin: 0, fontSize: 20, marginBottom: 16 }}>Radiologist Roster</h1>
      {roster.error && <div style={{ color: "var(--status-critical)" }}>{roster.error}</div>}
      {roster.data && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr>
              {COLUMNS.map((c) => (
                <th
                  key={c.key}
                  style={{
                    textAlign: "left",
                    color: "var(--text-muted)",
                    borderBottom: "1px solid var(--gridline)",
                    padding: "8px 12px",
                    fontWeight: 500,
                  }}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {roster.data.map((row) => (
              <tr key={row.npi}>
                {COLUMNS.map((c) => (
                  <td
                    key={c.key}
                    style={{
                      padding: "8px 12px",
                      borderBottom: "1px solid var(--gridline)",
                      color: "var(--text-primary)",
                    }}
                  >
                    {(row as unknown as Record<string, string | null>)[c.key] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
