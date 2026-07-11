import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { MitigationPanel } from "../components/MitigationPanel";
import { ResponseDiff } from "../components/ResponseDiff";
import {
  TrajectoryGraph,
  TrajectoryNodeCard,
  getTrajectoryStepLabel,
} from "../components/TrajectoryGraph";
import type { ComparisonResponse, TrajectoryStepDef } from "../types";
import { getFaultTypeName } from "../lib/faultTypes";

interface ComparisonWorkbenchProps {
  comparison: ComparisonResponse;
  onComparisonUpdate: (updated: ComparisonResponse) => void;
  liveMode: boolean;
}

function formatFaultLabel(faultType: string | undefined): string {
  return getFaultTypeName(faultType);
}

function findInjectionStep(trajectory: TrajectoryStepDef[]): TrajectoryStepDef | undefined {
  return trajectory.find(
    (s) => s.step_type === "tool_response" && s.data.injected_response != null
  );
}

function describeRecoveryAction(action: string | null | undefined): string {
  switch (action) {
    case "recovered":
      return "Recovered";
    case "safe_abort":
      return "Safe abort";
    case "propagated":
      return "Propagated fault";
    case "crashed":
      return "Crashed";
    default:
      return "No clear recovery";
  }
}

function diagnosticBadgeClass(tone: "pass" | "fail" | "neutral"): string {
  if (tone === "pass") {
    return "badge leg-b-badge pass";
  }
  if (tone === "fail") {
    return "badge leg-b-badge fail";
  }
  return "badge leg-b-badge outcome-badge diagnostic";
}

function recoveryTone(action: string | null | undefined): "pass" | "fail" | "neutral" {
  switch (action) {
    case "recovered":
      return "pass";
    case "propagated":
    case "crashed":
      return "fail";
    default:
      return "neutral";
  }
}

function firstCheckDescription(
  checks: { description: string; passed: boolean }[],
  passed: boolean
): string | null {
  return checks.find((check) => check.passed === passed)?.description ?? null;
}

function describeAlignedRow(
  cleanStep: TrajectoryStepDef | undefined,
  faultedStep: TrajectoryStepDef | undefined,
  rowIndex: number,
  divergenceIndex: number | null
): string {
  if (cleanStep && faultedStep) {
    if (divergenceIndex != null && rowIndex === divergenceIndex) {
      if (
        faultedStep.step_type === "tool_response" &&
        faultedStep.data.injected_response != null
      ) {
        return `Step ${rowIndex + 1}: injected response`;
      }
      if (faultedStep.step_type === "llm_generation") {
        return `Step ${rowIndex + 1}: diverged reasoning`;
      }
      if (faultedStep.step_type === "final_answer") {
        return `Step ${rowIndex + 1}: diverged final answer`;
      }
      return `Step ${rowIndex + 1}: diverged ${getTrajectoryStepLabel(faultedStep).toLowerCase()}`;
    }

    if (cleanStep.step_type === faultedStep.step_type) {
      return `Step ${rowIndex + 1}: aligned ${getTrajectoryStepLabel(faultedStep).toLowerCase()}`;
    }
    return `Step ${rowIndex + 1}: aligned comparison`;
  }

  if (cleanStep) {
    return `Step ${rowIndex + 1}: only in clean run`;
  }
  if (faultedStep) {
    return `Step ${rowIndex + 1}: only in faulted run`;
  }
  return `Step ${rowIndex + 1}`;
}

export function ComparisonWorkbench({
  comparison,
  onComparisonUpdate,
  liveMode,
}: ComparisonWorkbenchProps) {
  const [selectedStep, setSelectedStep] = useState<{
    source: "clean" | "faulted" | "mitigated";
    step: TrajectoryStepDef;
  } | null>(null);
  const [mitigating, setMitigating] = useState(false);
  const [mitigationError, setMitigationError] = useState<string | null>(null);
  const [showTraces, setShowTraces] = useState(false);
  const [showMitigatedTraces, setShowMitigatedTraces] = useState(false);
  const [pendingShowTraces, setPendingShowTraces] = useState(false);
  const mitigatedSectionRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (pendingShowTraces && comparison.mitigated_trajectory) {
      mitigatedSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
      setPendingShowTraces(false);
    }
  }, [pendingShowTraces, comparison.mitigated_trajectory]);

  const handleShowMitigatedTraces = () => {
    setShowMitigatedTraces(true);
    setPendingShowTraces(true);
  };

  const injectionStep = findInjectionStep(comparison.faulted_trajectory);
  const divergenceIndex = comparison.divergence.node_index;
  const pairedRowCount = Math.max(
    comparison.clean_trajectory.length,
    comparison.faulted_trajectory.length
  );

  const primaryChecksFaulted = comparison.primary_checks_faulted;
  const diagnosticsFaulted = comparison.diagnostics_faulted;
  const primaryChecksMitigated = comparison.primary_checks_mitigated;
  const faultChecksPassed = primaryChecksFaulted.every((check: any) => check.passed);
  const failedCheckCount = primaryChecksFaulted.filter((check: any) => !check.passed).length;
  const faultLabel = formatFaultLabel(comparison.fault?.fault_type);
  const faultToolId = comparison.fault?.tool_id ?? comparison.injection_point.tool_id;
  const faultOccurrence = comparison.fault?.occurrence ?? comparison.injection_point.occurrence;
  const firstPassedCheck = firstCheckDescription(primaryChecksFaulted, true);
  const firstFailedCheck = firstCheckDescription(primaryChecksFaulted, false);

  // This banner always describes the ORIGINAL clean-vs-faulted comparison,
  // never the mitigation outcome — that has its own summary next to the
  // mitigated run section below, so the two don't get conflated.
  let summaryTitle = "Faulted run passed";
  let summaryTone: "is-warning" | "is-stable" = "is-stable";
  let summaryCopy = `The injected ${faultLabel} ${
    comparison.divergence.diverged ? "changed the trajectory," : "did not change the trajectory,"
  } and the faulted run passed the primary pass/fail checks${
    firstPassedCheck ? `: ${firstPassedCheck}` : "."
  }`;

  if (!faultChecksPassed) {
    summaryTitle = "Faulted run failed";
    summaryTone = "is-warning";
    summaryCopy = `The injected ${faultLabel} ${
      comparison.divergence.diverged ? "changed the trajectory and " : ""
    }caused ${failedCheckCount} primary pass/fail check${
      failedCheckCount === 1 ? "" : "s"
    } to fail${firstFailedCheck ? `: ${firstFailedCheck}` : "."}`;
  }

  const selectStep = (
    source: "clean" | "faulted" | "mitigated",
    step: TrajectoryStepDef
  ) => setSelectedStep({ source, step });

  const handleRunMitigation = async (mitigation: {
    retry_backoff: boolean;
    schema_validation: boolean;
    injection_scanner: boolean;
    output_verifier: boolean;
  }) => {
    if (!comparison.mcp_server_url || !comparison.model || !comparison.harness || !comparison.task || !comparison.fault) {
      setMitigationError("This comparison cannot be re-run with mitigation.");
      return;
    }
    setMitigating(true);
    setMitigationError(null);
    try {
      const updated = await api.runWorkbench(
        comparison.mcp_server_url,
        comparison.model,
        comparison.harness,
        comparison.task,
        comparison.fault,
        mitigation
      );

      // Preserve the faulted baseline from this comparison; only refresh the mitigated outcome.
      const failedBaselineIds = new Set(
        comparison.primary_checks_faulted.filter((check: any) => !check.passed).map((check: any) => check.check_id)
      );
      const passedMitigatedIds = new Set(
        (updated.primary_checks_mitigated ?? []).filter((check: any) => check.passed).map((check: any) => check.check_id)
      );
      const fixConfirmed =
        failedBaselineIds.size > 0 &&
        [...failedBaselineIds].every((id) => passedMitigatedIds.has(id));

      const merged: ComparisonResponse = {
        ...comparison,
        mitigated_trajectory: updated.mitigated_trajectory,
        mitigated_final_answer: updated.mitigated_final_answer,
        mitigated_run_error: updated.mitigated_run_error,
        primary_checks_mitigated: updated.primary_checks_mitigated,
        diagnostics_mitigated: updated.diagnostics_mitigated,
        fix_confirmed: fixConfirmed,
      };
      onComparisonUpdate(merged);
      if (merged.mitigated_trajectory) {
        setShowMitigatedTraces(false);
        setPendingShowTraces(true);
      }
    } catch (err) {
      setMitigationError(err instanceof Error ? err.message : "Mitigated run failed.");
    } finally {
      setMitigating(false);
    }
  };

  const handleToggleTraces = () => {
    setShowTraces((value) => {
      const next = !value;
      if (!next) {
        setSelectedStep(null);
      }
      return next;
    });
  };

  return (
    <div className="comparison-workbench">
      <div className="divergence-banner" role="status">
        <div className="divergence-banner-head">
          <span className={`divergence-banner-eyebrow ${summaryTone}`}>
            {summaryTitle}
          </span>
          <span className="divergence-banner-callout">
            {comparison.clean_trajectory.length} vs. {comparison.faulted_trajectory.length} steps
          </span>
        </div>
        <p className="divergence-banner-copy">{summaryCopy}</p>
        <div className="divergence-summary-badges">
          <span className={`badge ${faultChecksPassed ? "pass" : "fail"}`}>
            {faultChecksPassed ? "Primary checks passed" : "Primary checks failed"}
          </span>
          {diagnosticsFaulted && (
            <>
              <span className={diagnosticBadgeClass(recoveryTone(diagnosticsFaulted.recovery_action))}>
                Recovery: {describeRecoveryAction(diagnosticsFaulted.recovery_action)}
              </span>
            </>
          )}
        </div>
        {comparison.fault_spec && (
          <div className="divergence-fault-line">
            <span className="divergence-fault-label">Injected fault</span>
            <code>{faultLabel}</code>
            <span className="divergence-fault-label">into</span>
            <code>{faultToolId}</code>
            <span className="divergence-fault-label">on use #{faultOccurrence}</span>
          </div>
        )}
      </div>

      <div className="leg-checks-panel comparison-surface">
        <h3 className="comparison-column-title">Primary pass/fail checks</h3>
        <p className="config-card-desc">
          Deterministic checks for whether the agent handled the injected fault correctly.
        </p>
        {primaryChecksFaulted.length === 0 ? (
          <p className="config-card-desc leg-empty-state">
            No primary pass/fail checks apply to this fault type.
          </p>
        ) : (
          <ul className="leg-a-list">
            {primaryChecksFaulted.map((check: any) => (
              <li key={check.check_id} className={check.passed ? "leg-a-pass" : "leg-a-fail"}>
                <span className="leg-a-icon">{check.passed ? "\u2713" : "\u2717"}</span>
                <span>{check.description}</span>
              </li>
            ))}
          </ul>
        )}

        {diagnosticsFaulted && (
          <div className="leg-b-panel">
            <h4 className="leg-b-title">Diagnostic labels</h4>
            <p className="config-card-desc">
              LLM-judged labels summarizing failure detection, recovery, and uncertainty.
            </p>
            <div className="leg-b-badges">
              <span className={diagnosticBadgeClass(diagnosticsFaulted.failure_detected ? "pass" : "neutral")}>
                Problem acknowledged: {diagnosticsFaulted.failure_detected ? "Yes" : "No"}
              </span>
              <span className={diagnosticBadgeClass(recoveryTone(diagnosticsFaulted.recovery_action))}>
                Recovery: {describeRecoveryAction(diagnosticsFaulted.recovery_action)}
              </span>
              <span
                className={diagnosticBadgeClass(diagnosticsFaulted.uncertainty_communicated ? "pass" : "neutral")}
              >
                Uncertainty stated: {diagnosticsFaulted.uncertainty_communicated ? "Yes" : "No"}
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="comparison-surface trace-toggle-panel">
        <div className="trace-toggle-header">
          <div>
            <h3 className="comparison-column-title">Trace comparison</h3>
            <p className="config-card-desc">
              Optional step-level trace view for debugging. Open it when you need to inspect the
              aligned clean and faulted trajectories.
            </p>
          </div>
          <button type="button" className="config-inline-action" onClick={handleToggleTraces}>
            {showTraces ? "Hide traces" : "Show traces"}
          </button>
        </div>
      </div>

      {showTraces && (
        <>
          <div className="comparison-columns comparison-columns-aligned">
            <div className="comparison-columns-header">
              <div className="comparison-column comparison-column-clean comparison-column-shell">
                <h3 className="comparison-column-title">Clean run</h3>
                <p className="comparison-column-subtitle">
                  Baseline execution · {comparison.clean_trajectory.length} steps
                </p>
                {comparison.clean_run_error && (
                  <p className="run-error-notice">Run failed: {comparison.clean_run_error}</p>
                )}
              </div>
              <div className="comparison-column comparison-column-faulted comparison-column-shell">
                <h3 className="comparison-column-title">Faulted run</h3>
                <p className="comparison-column-subtitle">
                  Fault injected · {comparison.faulted_trajectory.length} steps
                </p>
                {comparison.faulted_run_error && (
                  <p className="run-error-notice">Run failed: {comparison.faulted_run_error}</p>
                )}
              </div>
            </div>
            {Array.from({ length: pairedRowCount }).map((_, rowIndex) => {
              const cleanStep = comparison.clean_trajectory[rowIndex];
              const faultedStep = comparison.faulted_trajectory[rowIndex];

              return (
                <div className="comparison-step-row-wrap" key={`row-${rowIndex}`}>
                  <div className="comparison-step-row-label">
                    {describeAlignedRow(cleanStep, faultedStep, rowIndex, divergenceIndex)}
                  </div>
                  <div className="comparison-step-row">
                    <div
                      className={`comparison-step-cell ${rowIndex > 0 ? "has-previous" : ""}`}
                    >
                      {cleanStep ? (
                        <TrajectoryNodeCard
                          step={cleanStep}
                          variant="clean"
                          isSelected={
                            selectedStep?.source === "clean" &&
                            selectedStep.step.index === cleanStep.index
                          }
                          onSelectStep={(step) => selectStep("clean", step)}
                        />
                      ) : (
                        <div className="trajectory-node-spacer" aria-hidden="true" />
                      )}
                    </div>
                    <div
                      className={`comparison-step-cell ${rowIndex > 0 ? "has-previous" : ""}`}
                    >
                      {faultedStep ? (
                        <TrajectoryNodeCard
                          step={faultedStep}
                          variant="faulted"
                          isDivergenceNode={divergenceIndex != null && rowIndex === divergenceIndex}
                          isSelected={
                            selectedStep?.source === "faulted" &&
                            selectedStep.step.index === faultedStep.index
                          }
                          onSelectStep={(step) => selectStep("faulted", step)}
                        />
                      ) : (
                        <div className="trajectory-node-spacer" aria-hidden="true" />
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {injectionStep && (
            <div className="injection-diff-panel comparison-surface">
              <h3 className="comparison-column-title">Clean vs. injected tool response</h3>
              <ResponseDiff
                clean={
                  (typeof injectionStep.data.clean_response === "object"
                    ? injectionStep.data.clean_response
                    : { value: injectionStep.data.clean_response }) as Record<string, unknown>
                }
                injected={
                  (typeof injectionStep.data.injected_response === "object"
                    ? injectionStep.data.injected_response
                    : { value: injectionStep.data.injected_response }) as Record<string, unknown>
                }
              />
            </div>
          )}

          {selectedStep?.step && (
            <div className="selected-step-panel comparison-surface">
              <div className="selected-step-header">
                <h4 className="selected-step-title">
                  Step detail ({selectedStep.source} · {selectedStep.step.step_type})
                </h4>
                <button
                  type="button"
                  className="kv-remove-btn"
                  onClick={() => setSelectedStep(null)}
                >
                  &times;
                </button>
              </div>
              <pre className="response-box selected-step-code">
                {JSON.stringify(selectedStep.step.data, null, 2)}
              </pre>
            </div>
          )}

        </>
      )}

      <MitigationPanel
        comparison={comparison}
        onRunMitigation={handleRunMitigation}
        onShowTraces={handleShowMitigatedTraces}
        running={mitigating}
        disabled={!liveMode || !comparison.mcp_server_url}
        disabledReason={
          !liveMode
            ? "Switch to Connect and run a live comparison to try mitigations."
            : undefined
        }
      />
      {mitigationError && (
        <p className="upload-errors" role="alert">
          {mitigationError}
        </p>
      )}

      {comparison.mitigated_trajectory && (
        <div
          className="comparison-column comparison-column-mitigated comparison-surface"
          style={{ marginTop: "1.5rem" }}
          ref={mitigatedSectionRef}
        >
          <h3 className="comparison-column-title">Redone with mitigation</h3>
          {primaryChecksMitigated && (
            <ul className="leg-a-list" style={{ marginBottom: "1rem" }}>
              {primaryChecksMitigated.map((check: any) => (
                <li key={check.check_id} className={check.passed ? "leg-a-pass" : "leg-a-fail"}>
                  <span className="leg-a-icon">{check.passed ? "\u2713" : "\u2717"}</span>
                  <span>{check.description}</span>
                </li>
              ))}
            </ul>
          )}

          <div className="trace-toggle-header">
            <div>
              <h3 className="comparison-column-title">Mitigated run trace</h3>
              <p className="config-card-desc">
                Optional step-level trace for the mitigated rerun · {comparison.mitigated_trajectory.length} steps
              </p>
            </div>
            <button
              type="button"
              className="config-inline-action"
              onClick={() =>
                setShowMitigatedTraces((value) => {
                  const next = !value;
                  if (!next && selectedStep?.source === "mitigated") {
                    setSelectedStep(null);
                  }
                  return next;
                })
              }
            >
              {showMitigatedTraces ? "Hide mitigated traces" : "Show mitigated traces"}
            </button>
          </div>

          {showMitigatedTraces && (
            <>
              <TrajectoryGraph
                trajectory={comparison.mitigated_trajectory}
                variant="mitigated"
                onSelectStep={(step) => selectStep("mitigated", step)}
                selectedIndex={
                  selectedStep?.source === "mitigated"
                    ? comparison.mitigated_trajectory.findIndex(
                        (step) => step.index === selectedStep.step.index
                      )
                    : null
                }
              />
              {selectedStep?.step && selectedStep.source === "mitigated" && (
                <div className="selected-step-panel" style={{ marginTop: "1rem" }}>
                  <div className="selected-step-header">
                    <h4 className="selected-step-title">
                      Step detail ({selectedStep.source} · {selectedStep.step.step_type})
                    </h4>
                    <button
                      type="button"
                      className="kv-remove-btn"
                      onClick={() => setSelectedStep(null)}
                    >
                      &times;
                    </button>
                  </div>
                  <pre className="response-box selected-step-code">
                    {JSON.stringify(selectedStep.step.data, null, 2)}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
