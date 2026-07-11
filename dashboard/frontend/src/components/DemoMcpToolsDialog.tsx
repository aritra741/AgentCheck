import { useEffect, useRef } from "react";

export interface DemoMcpTool {
  value: string;
  name: string;
  description: string;
}

export const DEMO_MCP_TOOLS: DemoMcpTool[] = [
  {
    value: "search_docs",
    name: "Search documents",
    description: "Search incident and operations documents to find a relevant brief id.",
  },
  {
    value: "get_incident_brief",
    name: "Get incident brief",
    description: "Return the full brief for a doc_id, including summary, root cause, status, and timeline.",
  },
  {
    value: "fetch_meta",
    name: "Fetch metadata",
    description: "Return document metadata such as owner, priority, service, and resolution time.",
  },
];

interface DemoMcpToolsDialogProps {
  open: boolean;
  onClose: () => void;
}

export function DemoMcpToolsDialog({ open, onClose }: DemoMcpToolsDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
    }
    if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="tools-dialog"
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialogRef.current) {
          onClose();
        }
      }}
    >
      <div className="tools-dialog-panel">
        <header className="tools-dialog-header">
          <div>
            <h2 className="tools-dialog-title">Demo MCP tools</h2>
            <p className="tools-dialog-subtitle">Tools exposed by the built-in incident-brief server.</p>
          </div>
          <button type="button" className="tools-dialog-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <ul className="tools-dialog-list">
          {DEMO_MCP_TOOLS.map((tool) => (
            <li key={tool.value} className="tools-dialog-item">
              <div className="tools-dialog-item-head">
                <span className="tools-dialog-item-name">{tool.name}</span>
                <code className="tools-dialog-item-id">{tool.value}</code>
              </div>
              <p className="tools-dialog-item-desc">{tool.description}</p>
            </li>
          ))}
        </ul>
      </div>
    </dialog>
  );
}
