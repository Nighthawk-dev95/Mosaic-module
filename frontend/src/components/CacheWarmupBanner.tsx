import { useEffect, useState } from "react";
import { mosaicApi } from "../api/client";

// A dataset counts as "touched" once this process has either cached it or recorded a
// permanent error for it (e.g. the known draft_insights_raw gap) - that dataset's own tab
// is as populated as it'll ever get this cycle, so it shouldn't keep the banner up forever.
export function CacheWarmupBanner() {
  const [touched, setTouched] = useState<number | null>(null);
  const [total, setTotal] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await mosaicApi.getRefreshStatus();
        if (cancelled) return;
        setTouched(Object.keys(res.refreshed_at).length + Object.keys(res.errors).length);
        setTotal(res.total_datasets);
      } catch {
        // leave previous state - a transient poll failure shouldn't flash the banner on/off
      }
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (touched === null || total === null || touched >= total) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 24px",
        background: "color-mix(in srgb, var(--status-warning) 18%, var(--surface-1))",
        borderBottom: "1px solid var(--status-warning)",
        fontSize: 13,
        color: "var(--text-primary)",
      }}
    >
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--status-warning)", flexShrink: 0 }} />
      <span>
        This app just restarted (a deploy resets its cache) - still loading data, {touched} / {total} modules ready.
        Some tabs below may look empty for a few more minutes.
      </span>
    </div>
  );
}
