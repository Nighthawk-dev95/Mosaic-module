import type { CSSProperties } from "react";

export const TABLE_SECTION_STYLE: CSSProperties = {
  background: "var(--surface-1)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: 16,
  display: "flex",
  flexDirection: "column",
  flex: "1 1 520px",
  minHeight: 520,
};

export const TABLE_SCROLL_STYLE: CSSProperties = {
  flex: 1,
  minHeight: 0,
  overflow: "auto",
};
