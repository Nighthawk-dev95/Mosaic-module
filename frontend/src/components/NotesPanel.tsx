import { useState } from "react";
import { mosaicApi } from "../api/client";
import { useFetch } from "../hooks/useFetch";
import { CARD_STYLE } from "../styles/glassCard";

interface NotesPanelProps {
  entityType: "radiologist" | "practice";
  entityKey: string;
}

// Matches PCC's own notes/journal system in spirit (a real, first-class note object attached
// to an entity, not a throwaway textarea) - scoped to radiologist/practice entities for this
// pass, see the plan file for what's explicitly deferred (cross-entity search, other entity
// types).
export function NotesPanel({ entityType, entityKey }: NotesPanelProps) {
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const list = useFetch(() => mosaicApi.getNotes(entityType, entityKey), [entityType, entityKey, refreshKey]);

  async function handleSave() {
    if (!draft.trim()) return;
    setSaving(true);
    try {
      await mosaicApi.postNote(entityType, entityKey, draft.trim());
      setDraft("");
      setRefreshKey((k) => k + 1);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={`Add a note about this ${entityType}...`}
          rows={3}
          style={{
            background: "var(--surface-raised)",
            border: "var(--glass-border)",
            borderRadius: "var(--radius)",
            color: "var(--text-primary)",
            padding: 10,
            fontSize: 13,
            fontFamily: "inherit",
            resize: "vertical",
          }}
        />
        <button
          onClick={handleSave}
          disabled={saving || !draft.trim()}
          style={{
            alignSelf: "flex-end",
            padding: "6px 14px",
            borderRadius: "var(--radius)",
            border: "none",
            background: "var(--color-primary)",
            color: "var(--page-plane)",
            fontSize: 13,
            fontWeight: 600,
            cursor: saving || !draft.trim() ? "not-allowed" : "pointer",
            opacity: saving || !draft.trim() ? 0.5 : 1,
          }}
        >
          {saving ? "Saving..." : "Add note"}
        </button>
      </div>

      {list.loading && <div style={{ color: "var(--text-muted)", fontSize: 13 }}>Loading notes...</div>}
      {list.error && <div style={{ color: "var(--status-critical)", fontSize: 13 }}>{list.error}</div>}
      {!list.loading && (list.data?.length ?? 0) === 0 && (
        <div style={{ color: "var(--text-muted)", fontSize: 13 }}>No notes yet.</div>
      )}
      {(list.data ?? []).map((n, i) => (
        <div key={i} style={{ ...CARD_STYLE, padding: 12 }}>
          <div style={{ fontSize: 13, whiteSpace: "pre-wrap" }}>{n.note_text}</div>
          <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 6 }}>
            {new Date(n.created_at).toLocaleString()}
          </div>
        </div>
      ))}
    </div>
  );
}
