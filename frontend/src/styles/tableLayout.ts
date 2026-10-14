import type { CSSProperties } from "react";

export const TABLE_SECTION_STYLE: CSSProperties = {
  background: "var(--glass-fill-card)",
  backdropFilter: "blur(var(--glass-blur-md))",
  WebkitBackdropFilter: "blur(var(--glass-blur-md))",
  border: "var(--glass-border)",
  boxShadow: "var(--glass-shadow-card), var(--glass-highlight)",
  borderRadius: "var(--radius-lg)",
  padding: "var(--space-16)",
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
