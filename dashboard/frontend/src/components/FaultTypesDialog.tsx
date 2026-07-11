import { useEffect, useRef } from "react";
import { FAULT_TYPE_CATEGORIES, FAULT_TYPES } from "../lib/faultTypes";

interface FaultTypesDialogProps {
  open: boolean;
  onClose: () => void;
}

export function FaultTypesDialog({ open, onClose }: FaultTypesDialogProps) {
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
            <h2 className="tools-dialog-title">Fault types</h2>
            <p className="tools-dialog-subtitle">
              Failures AgentCheck can inject into a tool response during a comparison run.
            </p>
          </div>
          <button type="button" className="tools-dialog-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="tools-dialog-list">
          {FAULT_TYPE_CATEGORIES.map((category) => (
            <section key={category} className="fault-types-section">
              <h3 className="fault-types-section-title">{category}</h3>
              <ul className="fault-types-section-list">
                {FAULT_TYPES.filter((fault) => fault.category === category).map((fault) => (
                  <li key={fault.value} className="tools-dialog-item">
                    <div className="tools-dialog-item-head">
                      <span className="tools-dialog-item-name">{fault.name}</span>
                    </div>
                    <p className="tools-dialog-item-desc">{fault.description}</p>
                    <p className="fault-types-pass-criterion">Pass if: {fault.passCriterion}</p>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </dialog>
  );
}
