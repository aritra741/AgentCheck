import { useEffect, useRef } from "react";
import { DEFAULT_DEMO_TASK } from "../lib/taskGuidance";

interface ReadFirstDialogProps {
  open: boolean;
  onClose: () => void;
  onSelectDefault: () => void;
}

export function ReadFirstDialog({ open, onClose, onSelectDefault }: ReadFirstDialogProps) {
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

  const handleSelectDefault = () => {
    onSelectDefault();
    onClose();
  };

  return (
    <dialog
      ref={dialogRef}
      className="tools-dialog tools-dialog-wide read-first-dialog"
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
            <h2 className="tools-dialog-title">Before you run this demo</h2>
            <p className="tools-dialog-subtitle">One recommendation, then you're set.</p>
          </div>
          <button type="button" className="tools-dialog-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="read-first-dialog-body">
          <p className="read-first-lead">
            For a quick inspection, we recommend using either the default task or tasks from the
            given list.
          </p>
          <p className="read-first-inline-note" role="note">
            Choose a tool that the agent needs to use to do the task. Otherwise no fault is
            injected.
          </p>
          <div className="read-first-task-preview">
            <span className="read-first-task-label">Default task</span>
            <p className="read-first-task-text">{DEFAULT_DEMO_TASK.task}</p>
            <span className="read-first-task-tool">
              Fault is injected into <code>{DEFAULT_DEMO_TASK.targetToolId}</code> only
            </span>
          </div>
          <p className="read-first-note">
            You can explore the other example tasks or plug in your own MCP server afterward.
          </p>
          <div className="read-first-actions">
            <button type="button" className="primary read-first-use-btn" onClick={handleSelectDefault}>
              Load the default task
            </button>
            <button type="button" className="read-first-skip-btn" onClick={onClose}>
              I'll pick my own
            </button>
          </div>
        </div>
      </div>
    </dialog>
  );
}
