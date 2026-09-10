import { useEffect, useState } from "react";
import { mosaicApi } from "../api/client";
import { Badge } from "./Badge";

function oldestTimestamp(refreshedAt: Record<string, string>): Date | null {
  const values = Object.values(refreshedAt);
  if (values.length === 0) return null;
  return new Date(Math.min(...values.map((v) => new Date(v).getTime())));
}

export function RefreshStatus() {
  const [status, setStatus] = useState<{ oldest: Date | null; inProgress: boolean; hasData: boolean } | null>(null);
  const [triggering, setTriggering] = useState(false);

  const poll = async () => {
    try {
      const res = await mosaicApi.getRefreshStatus();
      setStatus({
        oldest: oldestTimestamp(res.refreshed_at),
        inProgress: res.in_progress,
        hasData: Object.keys(res.refreshed_at).length > 0,
      });
    } catch {
      setStatus(null);
    }
  };

  useEffect(() => {
    poll();
    const id = setInterval(poll, 15000);
    return () => clearInterval(id);
  }, []);

  const handleRefresh = async () => {
    setTriggering(true);
    try {
      await mosaicApi.triggerRefresh();
      await poll();
    } finally {
      setTriggering(false);
    }
  };

  const label = !status || !status.hasData
    ? "No data loaded yet"
    : status.inProgress
      ? "Refreshing…"
      : `Data through ${status.oldest?.toLocaleDateString()}`;
  const color = !status || !status.hasData ? "var(--text-muted)" : status.inProgress ? "var(--status-warning)" : "var(--status-good)";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <Badge label={label} color={color} dot />
      <button
        onClick={handleRefresh}
        disabled={triggering || status?.inProgress}
        title="Trigger a manual refresh"
        style={{
          fontSize: 11,
          padding: "3px 8px",
          borderRadius: 999,
          border: "1px solid var(--border)",
          background: "var(--surface-raised)",
          color: "var(--text-secondary)",
          cursor: triggering || status?.inProgress ? "default" : "pointer",
        }}
      >
        {triggering || status?.inProgress ? "…" : "Refresh"}
      </button>
    </div>
  );
}
