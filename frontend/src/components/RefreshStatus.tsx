import { useEffect, useState } from "react";
import { mosaicApi } from "../api/client";

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

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
      <div style={{ color: "var(--text-muted)" }}>
        {!status || !status.hasData
          ? "No data loaded yet"
          : status.inProgress
            ? "Refreshing…"
            : `Data as of ${status.oldest?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`}
      </div>
      <button
        onClick={handleRefresh}
        disabled={triggering || status?.inProgress}
        style={{
          fontSize: 12,
          padding: "6px 10px",
          borderRadius: 6,
          border: "1px solid var(--border)",
          background: "var(--surface-raised)",
          color: "var(--text-secondary)",
          cursor: triggering || status?.inProgress ? "default" : "pointer",
        }}
      >
        {triggering || status?.inProgress ? "Refreshing…" : "Refresh Now"}
      </button>
    </div>
  );
}
