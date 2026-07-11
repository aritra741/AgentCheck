import { useState } from "react";
import type { TrajectoryStepDef } from "../types";

interface TrajectoryGraphProps {
  trajectory: TrajectoryStepDef[];
  variant: "clean" | "faulted" | "mitigated";
  divergenceIndex?: number | null;
  onSelectStep?: (step: TrajectoryStepDef) => void;
  selectedIndex?: number | null;
}

const PREVIEW_LIMIT = 180;

export function getTrajectoryStepLabel(step: TrajectoryStepDef): string {
  switch (step.step_type) {
    case "llm_generation":
      return "Reasoning step";
    case "tool_call":
      return "Tool call";
    case "tool_response":
      return "Tool response";
    case "final_answer":
      return "Final answer";
    default:
      return step.step_type;
  }
}

export function getTrajectoryStepPreview(step: TrajectoryStepDef): string {
  const data = step.data as Record<string, unknown>;
  if (step.step_type === "llm_generation") return String(data.completion ?? "");
  if (step.step_type === "tool_call") return JSON.stringify(data.tool_input ?? {});
  if (step.step_type === "tool_response") {
    if (data.mitigation_recovered && data.injected_response != null) {
      const injected =
        typeof data.injected_response === "string"
          ? data.injected_response
          : JSON.stringify(data.injected_response);
      const returned =
        data.returned_response ?? data.clean_response;
      const recovered =
        typeof returned === "string" ? returned : JSON.stringify(returned);
      return `Injected fault: ${injected}\nRecovered response: ${recovered}`;
    }
    const shown = data.injected_response ?? data.clean_response;
    return typeof shown === "string" ? shown : JSON.stringify(shown);
  }
  if (step.step_type === "final_answer") return String(data.answer ?? "");
  return "";
}

function isInjectedResponse(step: TrajectoryStepDef): boolean {
  return step.step_type === "tool_response" && step.data.injected_response != null;
}

function getFaultTag(step: TrajectoryStepDef): string {
  if (step.data.mitigation_recovered) {
    return `recovered from ${String(step.data.fault ?? "fault")}`;
  }
  return String(step.data.fault ?? "fault");
}

interface TrajectoryNodeCardProps {
  step: TrajectoryStepDef;
  variant: "clean" | "faulted" | "mitigated";
  isDivergenceNode?: boolean;
  isSelected?: boolean;
  onSelectStep?: (step: TrajectoryStepDef) => void;
}

function getStepMeta(step: TrajectoryStepDef): string | null {
  if (step.step_type === "tool_call" || step.step_type === "tool_response") {
    return typeof step.data.tool_id === "string" ? step.data.tool_id : null;
  }
  return null;
}

export function TrajectoryNodeCard({
  step,
  variant,
  isDivergenceNode = false,
  isSelected = false,
  onSelectStep,
}: TrajectoryNodeCardProps) {
  const [expanded, setExpanded] = useState(false);
  const preview = getTrajectoryStepPreview(step);
  const injected = variant !== "clean" && isInjectedResponse(step);
  const canExpand = preview.length > PREVIEW_LIMIT;
  const previewText = expanded || !canExpand ? preview : `${preview.slice(0, PREVIEW_LIMIT).trimEnd()}…`;
  const stepMeta = getStepMeta(step);
  const classes = [
    "trajectory-node",
    `trajectory-node-${step.step_type}`,
    injected ? "trajectory-node-injected" : "",
    isDivergenceNode ? "trajectory-node-divergence" : "",
    variant === "mitigated" ? "trajectory-node-mitigated" : "",
    isSelected ? "trajectory-node-selected" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes}>
      <button
        type="button"
        className="trajectory-node-select"
        onClick={() => onSelectStep?.(step)}
        aria-label={`${getTrajectoryStepLabel(step)}: ${preview}`}
      >
        {isDivergenceNode && (
          <span className="trajectory-divergence-flag">Trajectory diverges here</span>
        )}
        <span className="trajectory-node-header">
          <span className="trajectory-node-step-index">Step {step.index + 1}</span>
          {stepMeta && <span className="trajectory-node-step-meta">{stepMeta}</span>}
        </span>
        <span className="trajectory-node-label">{getTrajectoryStepLabel(step)}</span>
        <span className={`trajectory-node-preview ${expanded ? "expanded" : ""}`}>
          {previewText}
        </span>
        {injected && <span className="trajectory-node-fault-tag">{getFaultTag(step)}</span>}
      </button>
      {canExpand && (
        <button
          type="button"
          className="trajectory-node-show-more"
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "show less" : "show more"}
        </button>
      )}
    </div>
  );
}

export function TrajectoryGraph({
  trajectory,
  variant,
  divergenceIndex,
  onSelectStep,
  selectedIndex,
}: TrajectoryGraphProps) {
  return (
    <div className={`trajectory-graph trajectory-graph-${variant}`}>
      {trajectory.map((step, i) => {
        const isDivergenceNode =
          variant !== "clean" && divergenceIndex != null && i === divergenceIndex;

        return (
          <div className="trajectory-node-wrap" key={i}>
            {i > 0 && <div className="trajectory-edge" aria-hidden="true" />}
            <TrajectoryNodeCard
              step={step}
              variant={variant}
              isDivergenceNode={isDivergenceNode}
              isSelected={selectedIndex === i}
              onSelectStep={onSelectStep}
            />
          </div>
        );
      })}
    </div>
  );
}
