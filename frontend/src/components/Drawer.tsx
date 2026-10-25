import type { ReactNode } from "react";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
}

// Right-side slide-in panel using the --glass-fill-drawer/--glass-shadow-modal/--dur-drawer
// tokens already defined in theme.css from the earlier design-token merge, never used by any
// component until now. Inline styles, not the .glass-drawer CSS class - that class declares
// both -webkit-backdrop-filter and the unprefixed backdrop-filter in one rule, which the Vite/
// rolldown minifier silently drops the unprefixed one from (confirmed this session, fixed the
// same way in Sidebar.tsx/ReviewActivityTicker.tsx).
export function Drawer({ open, onClose, title, children }: DrawerProps) {
  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        zIndex: 100,
        display: "flex",
        justifyContent: "flex-end",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 420,
          maxWidth: "90vw",
          height: "100%",
          background: "var(--glass-fill-drawer)",
          backdropFilter: "blur(var(--glass-blur-md))",
          WebkitBackdropFilter: "blur(var(--glass-blur-md))",
          border: "var(--glass-border)",
          boxShadow: "var(--glass-shadow-modal), var(--glass-highlight)",
          padding: 20,
          overflowY: "auto",
          animation: `drawer-slide-in var(--dur-drawer) var(--ease-standard)`,
        }}
      >
        <style>{`@keyframes drawer-slide-in { from { transform: translateX(100%); } to { transform: translateX(0); } }`}</style>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          {title && <h2 style={{ margin: 0, fontSize: 16 }}>{title}</h2>}
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-secondary)",
              fontSize: 18,
              cursor: "pointer",
              lineHeight: 1,
            }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
