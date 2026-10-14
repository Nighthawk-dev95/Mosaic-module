import type { CSSProperties } from "react";

// Shared replacement for the CARD_STYLE literal that used to be duplicated verbatim across
// 7 page files - same glass recipe as PCC's own .glass-card utility class, as inline styles
// since this app's convention is all-inline (see DataTable.tsx's own note on that).
export const CARD_STYLE: CSSProperties = {
  background: "var(--glass-fill-card)",
  backdropFilter: "blur(var(--glass-blur-md))",
  WebkitBackdropFilter: "blur(var(--glass-blur-md))",
  border: "var(--glass-border)",
  boxShadow: "var(--glass-shadow-card), var(--glass-highlight)",
  borderRadius: "var(--radius-lg)",
  padding: "var(--space-16)",
};
