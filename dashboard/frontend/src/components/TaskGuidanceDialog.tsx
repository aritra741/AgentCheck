import { useEffect, useRef } from "react";
import {
  CUSTOM_TASK_EXAMPLE,
  CUSTOM_TASK_TIPS,
  DEMO_TASK_EXAMPLES,
  type TaskExample,
} from "../lib/taskGuidance";

interface TaskGuidanceDialogProps {
  open: boolean;
  mcpSource: "builtin" | "custom";
  onClose: () => void;
  onSelectExample: (example: TaskExample) => void;
}

function TaskExampleRow({
  example,
  onSelectExample,
  onClose,
}: {
  example: TaskExample;
  onSelectExample: (example: TaskExample) => void;
  onClose: () => void;
}) {
  return (
    <li className="tools-dialog-item task-guidance-item">
      <div className="tools-dialog-item-head">
        <span className="tools-dialog-item-name">{example.title}</span>
        <button
          type="button"
          className="task-guidance-use-btn"
          onClick={() => {
            onSelectExample(example);
            onClose();
          }}
        >
          Use this task
        </button>
      </div>
      <p className="tools-dialog-item-desc">{example.task}</p>
    </li>
  );
}

export function TaskGuidanceDialog({ open, mcpSource, onClose, onSelectExample }: TaskGuidanceDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const isBuiltin = mcpSource === "builtin";

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
      className="tools-dialog tools-dialog-wide"
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
            <h2 className="tools-dialog-title">Writing a task</h2>
            <p className="tools-dialog-subtitle">
              {isBuiltin
                ? "The task tells the agent what to do with the demo server's incident-brief tools."
                : "The task tells the agent what goal to pursue using your MCP server's tools."}
            </p>
          </div>
          <button type="button" className="tools-dialog-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="tools-dialog-list">
          {isBuiltin ? (
            <>
              <p className="task-guidance-note">
                The demo server includes one document: <strong>brief-11</strong> (Onboarding Incident
                Brief 11). Pick an example below or edit the task field directly.
              </p>
              <ul className="fault-types-section-list">
                {DEMO_TASK_EXAMPLES.map((example) => (
                  <TaskExampleRow
                    key={example.title}
                    example={example}
                    onSelectExample={onSelectExample}
                    onClose={onClose}
                  />
                ))}
              </ul>
            </>
          ) : (
            <>
              <ul className="task-guidance-tips">
                {CUSTOM_TASK_TIPS.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
              <ul className="fault-types-section-list">
                <TaskExampleRow
                  example={CUSTOM_TASK_EXAMPLE}
                  onSelectExample={onSelectExample}
                  onClose={onClose}
                />
              </ul>
            </>
          )}
        </div>
      </div>
    </dialog>
  );
}
