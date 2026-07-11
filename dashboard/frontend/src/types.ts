export interface ToolSpecDef {
  tool_id: string;
  description: string;
  input_format: Record<string, unknown>;
  output_format: Record<string, unknown> | string;
}

export interface AgentSpecDef {
  model: string;
  task: string;
  tools: ToolSpecDef[];
  harness: "react" | "native_tool_calling";
  provider?: string | null;
  base_url?: string | null;
  api_key_env?: string | null;
  max_steps: number;
  agent_id: string;
}

export interface InjectionPointDef {
  tool_id: string;
  occurrence: number;
}

export interface FaultSpecDef {
  action: string;
  params: Record<string, unknown>;
}

export interface WorkbenchFaultDef {
  fault_type: string;
  tool_id: string;
  occurrence: number;
}

export interface TrajectoryStepDef {
  index: number;
  step_type: "llm_generation" | "tool_call" | "tool_response" | "final_answer";
  data: Record<string, unknown>;
}

export interface LegACheckResultDef {
  check_id: string;
  description: string;
  passed: boolean;
}

export interface LegBResultDef {
  failure_detected: boolean;
  recovery_action: string;
  uncertainty_communicated: boolean;
  evidence: Record<string, string>;
  scoring_metadata: Record<string, unknown>;
}

export interface DivergenceDef {
  diverged: boolean;
  node_index: number | null;
  description: string;
}

export interface ComparisonResponse {
  example_id?: string;
  mcp_server_url?: string;
  model?: string;
  harness?: "react" | "native_tool_calling";
  task?: string;
  fault?: WorkbenchFaultDef;
  agent_spec: AgentSpecDef;
  fault_spec: FaultSpecDef;
  injection_point: InjectionPointDef;
  clean_trajectory: TrajectoryStepDef[];
  faulted_trajectory: TrajectoryStepDef[];
  mitigated_trajectory: TrajectoryStepDef[] | null;
  mitigated_final_answer?: string | null;
  divergence: DivergenceDef;
  leg_a_faulted: LegACheckResultDef[];
  leg_b_faulted: LegBResultDef | null;
  leg_a_mitigated: LegACheckResultDef[] | null;
  leg_b_mitigated: LegBResultDef | null;
  fix_confirmed: boolean | null;
  clean_run_error?: string | null;
  faulted_run_error?: string | null;
  mitigated_run_error?: string | null;
}

export interface ExampleSummary {
  example_id: string;
  fault_type: string;
  fault_action: string;
  task: string;
  model: string;
  harness: "react" | "native_tool_calling";
  tool_id: string;
}
