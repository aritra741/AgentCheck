import { useState } from "react";
import type { ComparisonResponse } from "../types";

interface MitigationState {
  retry_backoff: boolean;
  schema_validation: boolean;
  injection_scanner: boolean;
  output_verifier: boolean;
}

const MITIGATION_OPTIONS: {
  key: keyof MitigationState;
  label: string;
  typicallyAddresses: string;
}[] = [
  { key: "retry_backoff", label: "Retry with backoff", typicallyAddresses: "Timeouts, transient API errors" },
  { key: "schema_validation", label: "Schema validation", typicallyAddresses: "Schema drift" },
  { key: "injection_scanner", label: "Injection filter", typicallyAddresses: "Prompt injection, data exfiltration" },
  { key: "output_verifier", label: "Output verifier", typicallyAddresses: "Inconsistent output formats" },
];

interface MitigationPanelProps {
  comparison: ComparisonResponse;
  onRunMitigation: (mitigation: MitigationState) => Promise<void>;
  onShowTraces: () => void;
  running: boolean;
  disabled?: boolean;
  disabledReason?: string;
}

export function MitigationPanel({
  comparison,
  onRunMitigation,
  onShowTraces,
  running,
  disabled,
  disabledReason,
}: MitigationPanelProps) {
  const [mitigation, setMitigation] = useState<MitigationState>({
    retry_backoff: false,
    schema_validation: false,
    injection_scanner: false,
    output_verifier: false,
  });

  const toggle = (key: keyof MitigationState) =>
    setMitigation((prev) => ({ ...prev, [key]: !prev[key] }));

  const anySelected = Object.values(mitigation).some(Boolean);
  const failedCheckCount = comparison.primary_checks_faulted.filter((check) => !check.passed).length;
  const hadFaultedFailure = failedCheckCount > 0;
  const hasMitigatedRun = comparison.mitigated_trajectory != null;
  const showVerdict = hasMitigatedRun && hadFaultedFailure && !running;
  const verdictPassed = Boolean(comparison.fix_confirmed);

  return (
    <section className="mitigation-panel" style={{ marginTop: "2rem" }}>
      <h3 className="config-card-title">{hadFaultedFailure ? "Try a mitigation" : "No mitigation needed"}</h3>
      <p className="config-card-desc">
        {hadFaultedFailure
          ? `The faulted run failed ${failedCheckCount} primary pass/fail check${
              failedCheckCount === 1 ? "" : "s"
            }. Select a mitigation and re-run the same injected fault to see whether those failed checks now pass.`
          : "The faulted run passed all primary pass/fail checks. You can still test a mitigation, but there is no failed primary check to repair."}
      </p>

      <div className="mitigation-toggle-grid" style={{ marginBottom: "1rem" }}>
        {MITIGATION_OPTIONS.map((opt) => {
          const isSelected = mitigation[opt.key];
          return (
            <label
              key={opt.key}
              className={`mitigation-toggle-card ${isSelected ? "selected" : ""}`}
              style={{ position: "relative" }}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => toggle(opt.key)}
                className="mitigation-checkbox-hidden"
              />
              <div className="mitigation-toggle-label-row">
                <div className="mitigation-toggle-indicator" />
                <span className="mitigation-toggle-label">{opt.label}</span>
              </div>
              <span className="mitigation-toggle-note">
                Best for {opt.typicallyAddresses.toLowerCase()}
              </span>
            </label>
          );
        })}
      </div>

      <div className="mitigation-actions">
        <p className="mitigation-selection-note">
          {anySelected
            ? hadFaultedFailure
              ? "Ready to re-run the same injected fault."
              : "Ready to re-run the same injected fault, although there is no failed check to repair."
            : "Select at least one mitigation."}
        </p>
        <button
          type="button"
          className={`config-run-btn mitigation-run-btn ${anySelected ? "is-active" : "is-inactive"}`}
          disabled={running || !anySelected || disabled}
          onClick={() => void onRunMitigation(mitigation)}
          title={disabled ? disabledReason : undefined}
        >
          {running ? "Re-running with mitigation..." : "Re-run with mitigation"}
        </button>
      </div>
      {disabled && disabledReason && (
        <p className="config-footer-note" style={{ marginTop: "0.5rem", fontSize: "0.76rem", color: "var(--text-light)" }}>
          {disabledReason}
        </p>
      )}

      {showVerdict && (
        <p
          className={`mitigation-verdict-line ${verdictPassed ? "mitigation-verdict-pass" : "mitigation-verdict-fail"}`}
          role="status"
        >
          {verdictPassed ? (
            <>
              <strong>Mitigation passed:</strong> after re-running with mitigation, all previously
              failed primary pass/fail checks now pass.{" "}
              <button type="button" className="mitigation-verdict-link" onClick={onShowTraces}>
                Show traces
              </button>
            </>
          ) : (
            <>
              <strong>Mitigation failed:</strong> after re-running with mitigation, at least one
              primary pass/fail check still fails.{" "}
              <button type="button" className="mitigation-verdict-link" onClick={onShowTraces}>
                Show traces
              </button>
            </>
          )}
        </p>
      )}
    </section>
  );
}
