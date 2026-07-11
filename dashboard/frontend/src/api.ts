import { backendUrl } from "./lib/backendOrigin";
import type {
  ComparisonResponse,
  ExampleSummary,
  WorkbenchFaultDef,
} from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(backendUrl(path));
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(backendUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : JSON.stringify(data?.detail ?? data);
    throw new Error(message);
  }
  return data as T;
}

export const api = {
  listExamples: () => get<ExampleSummary[]>("/api/examples"),
  exampleComparison: (exampleId: string) => get<ComparisonResponse>(`/api/examples/${encodeURIComponent(exampleId)}`),
  runWorkbench: (
    mcpServerUrl: string,
    model: string,
    harness: "react" | "native_tool_calling",
    task: string,
    fault: WorkbenchFaultDef,
    mitigation?: {
      retry_backoff: boolean;
      schema_validation: boolean;
      injection_scanner: boolean;
      output_verifier: boolean;
    }
  ) =>
    post<ComparisonResponse>("/api/run", {
      mcp_server_url: mcpServerUrl,
      model,
      harness,
      task,
      fault,
      mitigation,
    }),
};
