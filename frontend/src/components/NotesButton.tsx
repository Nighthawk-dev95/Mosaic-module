import { useState } from "react";
import { Drawer } from "./Drawer";
import { NotesPanel } from "./NotesPanel";

interface NotesButtonProps {
  entityType: "radiologist" | "practice";
  entityKey: string;
  label?: string;
}

// Small affordance dropped into any table/row that represents an entity notes can attach to -
// opens a Drawer with the full NotesPanel rather than inlining notes everywhere they might
// apply.
export function NotesButton({ entityType, entityKey, label }: NotesButtonProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        title={`Notes for ${entityKey}`}
        style={{
          background: "transparent",
          border: "none",
          color: "var(--text-muted)",
          cursor: "pointer",
          fontSize: 13,
          padding: "2px 4px",
          transition: `color var(--dur-card) var(--ease-standard)`,
        }}
      >
        📝{label ? ` ${label}` : ""}
      </button>
      <Drawer open={open} onClose={() => setOpen(false)} title={`Notes — ${entityKey}`}>
        <NotesPanel entityType={entityType} entityKey={entityKey} />
      </Drawer>
    </>
  );
}
