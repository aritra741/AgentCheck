import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { DEMO_MCP_TOOLS, DemoMcpToolsDialog } from "../components/DemoMcpToolsDialog";
import { TargetToolField } from "../components/TargetToolField";
import { FaultTypesDialog } from "../components/FaultTypesDialog";
import { TaskGuidanceDialog } from "../components/TaskGuidanceDialog";
import { ReadFirstDialog } from "../components/ReadFirstDialog";
import { ComparisonWorkbench } from "./ComparisonWorkbench";
import { FAULT_TYPES, getFaultTypeName } from "../lib/faultTypes";
import { backendUrl, getBackendOrigin } from "../lib/backendOrigin";
import { DEFAULT_DEMO_TASK } from "../lib/taskGuidance";
import type { ComparisonResponse, ExampleSummary } from "../types";

const MODEL_OPTIONS = [
  { value: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  { value: "deepseek-v4-pro", label: "DeepSeek V4 Pro" },
  { value: "meta-llama/llama-3.3-70b-instruct", label: "Llama 3.3 70B" },
  { value: "gpt-4.1-mini", label: "GPT-4.1 mini" },
];

function defaultDemoMcpUrl(): string {
  const origin = getBackendOrigin();
  return origin ? backendUrl("/mcp") : "";
}

export function DefineAgent() {
  const [examples, setExamples] = useState<ExampleSummary[]>([]);
  const [mode, setMode] = useState<"connect" | "explore">("connect");
  const [mcpSource, setMcpSource] = useState<"builtin" | "custom">("builtin");
  const [mcpServerUrl, setMcpServerUrl] = useState(defaultDemoMcpUrl);
  const [model, setModel] = useState("meta-llama/llama-3.3-70b-instruct");
  const [harness, setHarness] = useState<"react" | "native_tool_calling">("react");
  const [task, setTask] = useState(
    "Open incident brief-11 and explain what caused the outage and whether it is still active."
  );
  const [targetToolId, setTargetToolId] = useState("get_incident_brief");
  const [injectionOccurrence, setInjectionOccurrence] = useState(1);
  const [faultType, setFaultType] = useState("A1");
  const [exampleSearch, setExampleSearch] = useState("");
  const [selectedExampleId, setSelectedExampleId] = useState<string | null>(null);

  const [running, setRunning] = useState(false);
  const [loadingExample, setLoadingExample] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comparison, setComparison] = useState<ComparisonResponse | null>(null);
  const [toolsDialogOpen, setToolsDialogOpen] = useState(false);
  const [faultTypesDialogOpen, setFaultTypesDialogOpen] = useState(false);
  const [taskGuidanceDialogOpen, setTaskGuidanceDialogOpen] = useState(false);
  const [readFirstOpen, setReadFirstOpen] = useState(false);
  const [taskJustApplied, setTaskJustApplied] = useState(false);

  const applyDefaultTask = useCallback(() => {
    setMode("connect");
    setMcpSource("builtin");
    setMcpServerUrl(defaultDemoMcpUrl());
    setTask(DEFAULT_DEMO_TASK.task);
    setTargetToolId(DEFAULT_DEMO_TASK.targetToolId ?? "get_incident_brief");
    setFaultType("A1");
    setInjectionOccurrence(1);
    setSelectedExampleId(null);
    setComparison(null);
    setTaskJustApplied(true);
    requestAnimationFrame(() => {
      document.getElementById("task")?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }, []);

  useEffect(() => {
    if (!taskJustApplied) return;
    const timer = window.setTimeout(() => setTaskJustApplied(false), 2200);
    return () => window.clearTimeout(timer);
  }, [taskJustApplied]);

  useEffect(() => {
    api.listExamples()
      .then(setExamples)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load form metadata."));
  }, []);

  const filteredExamples = useMemo(() => {
    const q = exampleSearch.trim().toLowerCase();
    if (!q) return examples.slice(0, 60);
    return examples.filter(
      (ex) =>
        ex.example_id.toLowerCase().includes(q) ||
        ex.fault_type.toLowerCase().includes(q) ||
        ex.task.toLowerCase().includes(q)
    );
  }, [examples, exampleSearch]);

  const builtinMcpUrl = useMemo(() => defaultDemoMcpUrl(), []);
  const effectiveMcpUrl = mcpSource === "builtin" ? builtinMcpUrl : mcpServerUrl;

  const handleMcpSourceChange = (source: "builtin" | "custom") => {
    setMcpSource(source);
    if (source === "builtin") {
      setMcpServerUrl(defaultDemoMcpUrl());
      if (!DEMO_MCP_TOOLS.some((tool) => tool.value === targetToolId)) {
        setTargetToolId("get_incident_brief");
      }
    }
  };

  const handleRun = async () => {
    setError(null);
    setComparison(null);
    setMode("connect");
    if (!effectiveMcpUrl.trim() || !task.trim() || !targetToolId.trim()) {
      setError("MCP server URL, task, and the tool to inject into are required.");
      return;
    }

    setRunning(true);
    try {
      const result = await api.runWorkbench(effectiveMcpUrl, model, harness, task, {
        fault_type: faultType,
        tool_id: targetToolId.trim(),
        occurrence: injectionOccurrence,
      });
      setComparison(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Workbench run failed.");
    } finally {
      setRunning(false);
    }
  };

  const loadExample = async (exampleId: string) => {
    setError(null);
    setLoadingExample(true);
    setSelectedExampleId(exampleId);
    setMode("explore");
    try {
      const result = await api.exampleComparison(exampleId);
      setComparison(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load example.");
    } finally {
      setLoadingExample(false);
    }
  };

  return (
    <div className="config-page">
      <div className="config-header">
        <span className="eyebrow">AgentCheck</span>
        <h2>Reproduce and debug MCP agent failures</h2>
        {/* <p>
          Compare clean and faulted trajectories, inspect injected response diffs, review primary
          pass/fail checks, and re-run with mitigations.
        </p> */}
      </div>

      <button type="button" className="read-first-banner" onClick={() => setReadFirstOpen(true)}>
        <span className="read-first-banner-icon" aria-hidden="true">
          i
        </span>
        <span className="read-first-banner-text">
          <strong>Please read this first</strong> for the fastest way to see the demo work.
        </span>
        <span className="read-first-banner-cta">Open</span>
      </button>

      <div className="config-tabs">
        <button
          type="button"
          className={`config-inline-action ${mode === "connect" ? "active" : ""}`}
          onClick={() => setMode("connect")}
        >
          Connect to an MCP server
        </button>
        <button
          type="button"
          className={`config-inline-action ${mode === "explore" ? "active" : ""}`}
          onClick={() => setMode("explore")}
        >
          Browse examples
        </button>
      </div>

      <div className="config-grid">
        <section className="config-panel-left">
          <div className="config-panel-scroll">
            {mode === "connect" ? (
              <>
                <h3 className="config-card-title">Configuration</h3>
                <p className="config-card-desc" style={{ marginBottom: "1rem" }}>
                  Use the built-in demo MCP or connect your own server, then choose a model,
                  execution style, task, fault type, injection target, and call number.
                </p>

                <aside className="injection-prerequisite" role="note">
                  <span className="injection-prerequisite-icon" aria-hidden="true">
                    !
                  </span>
                  <p className="injection-prerequisite-text">
                    <strong>Select a tool that is relevant to the task.</strong> Fault injection
                    works only if the agent needs to use that tool to do the task. If the task
                    does not use that tool, no fault is injected.
                  </p>
                </aside>

                <div className="form-field">
                  <label>MCP server</label>
                  <div className="config-tabs mcp-source-tabs">
                    <button
                      type="button"
                      className={`config-inline-action ${mcpSource === "builtin" ? "active" : ""}`}
                      onClick={() => handleMcpSourceChange("builtin")}
                    >
                      AgentCheck demo MCP
                    </button>
                    <button
                      type="button"
                      className={`config-inline-action ${mcpSource === "custom" ? "active" : ""}`}
                      onClick={() => handleMcpSourceChange("custom")}
                    >
                      Custom MCP server
                    </button>
                  </div>
                </div>

                {mcpSource === "builtin" ? (
                  <p className="config-footer-note mcp-source-hint">
                    Click{" "}
                    <button
                      type="button"
                      className="inline-text-link"
                      onClick={() => setToolsDialogOpen(true)}
                    >
                      here
                    </button>{" "}
                    to see the available tools.
                  </p>
                ) : (
                  <div className="form-field">
                    <label htmlFor="mcp-server-url">MCP server URL</label>
                    <input
                      id="mcp-server-url"
                      className="field-input"
                      value={mcpServerUrl}
                      onChange={(e) => setMcpServerUrl(e.target.value)}
                      placeholder="https://your-server.example/mcp"
                    />
                  </div>
                )}

                <div className="config-row config-row-two">
                  <div className="form-field">
                    <label htmlFor="model">Model</label>
                    <select
                      id="model"
                      className="field-select"
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                    >
                      {MODEL_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-field">
                    <label htmlFor="harness">Execution style</label>
                    <select
                      id="harness"
                      className="field-select"
                      value={harness}
                      onChange={(e) => setHarness(e.target.value as "react" | "native_tool_calling")}
                    >
                      <option value="react">ReAct</option>
                      <option value="native_tool_calling">Native tool calling</option>
                    </select>
                  </div>
                </div>

                <div className="form-field">
                  <label htmlFor="task">Task</label>
                  <textarea
                    id="task"
                    className={`field-input field-textarea ${taskJustApplied ? "field-flash" : ""}`}
                    rows={4}
                    value={task}
                    onChange={(e) => setTask(e.target.value)}
                    placeholder={
                      mcpSource === "builtin"
                        ? "Describe what the agent should find or report using the demo tools…"
                        : "Describe the goal the agent should accomplish with your MCP tools…"
                    }
                  />
                  <p className="config-footer-note">
                    Click{" "}
                    <button
                      type="button"
                      className="inline-text-link"
                      onClick={() => setTaskGuidanceDialogOpen(true)}
                    >
                      here
                    </button>{" "}
                    {mcpSource === "builtin"
                      ? "for example tasks paired with the right demo tool."
                      : "for guidance on writing a task for your MCP server."}
                  </p>
                </div>

                <div className="config-row">
                  <div className="form-field">
                    <label htmlFor="fault-type">Fault type</label>
                    <select
                      id="fault-type"
                      className="field-select"
                      value={faultType}
                      onChange={(e) => setFaultType(e.target.value)}
                    >
                      {FAULT_TYPES.map((fault) => (
                        <option key={fault.value} value={fault.value}>
                          {fault.name}
                        </option>
                      ))}
                    </select>
                    <p className="config-footer-note">
                      Click{" "}
                      <button
                        type="button"
                        className="inline-text-link"
                        onClick={() => setFaultTypesDialogOpen(true)}
                      >
                        here
                      </button>{" "}
                      to see what each fault type means.
                    </p>
                  </div>
                  <TargetToolField
                    value={targetToolId}
                    onChange={setTargetToolId}
                    choices={mcpSource === "builtin" ? DEMO_MCP_TOOLS : undefined}
                    placeholder="search_docs"
                    helperText={
                      mcpSource === "builtin" ? (
                        <>
                          Click{" "}
                          <button
                            type="button"
                            className="inline-text-link"
                            onClick={() => setToolsDialogOpen(true)}
                          >
                            here
                          </button>{" "}
                          to see what each tool does.
                        </>
                      ) : (
                        "Enter the name exactly as your MCP server exposes it."
                      )
                    }
                  />
                  <div className="form-field">
                    <label htmlFor="occurrence">Inject on call #</label>
                    <input
                      id="occurrence"
                      type="number"
                      min={1}
                      className="field-input"
                      value={injectionOccurrence}
                      onChange={(e) => setInjectionOccurrence(Math.max(1, parseInt(e.target.value, 10) || 1))}
                    />
                    <p className="config-footer-note">
                      Only this call is faulted (1 = first call).
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <>
                <h3 className="config-card-title">Examples</h3>
                <p className="config-card-desc" style={{ marginBottom: "1rem" }}>
                  Browse precomputed benchmark examples.
                </p>
                <input
                  className="field-input"
                  placeholder="Search examples by id, fault type, or task..."
                  value={exampleSearch}
                  onChange={(e) => setExampleSearch(e.target.value)}
                />
                <div className="example-grid" style={{ marginTop: "1rem" }}>
                  {filteredExamples.map((example) => {
                    const isSelected = selectedExampleId === example.example_id;
                    const isLoading = loadingExample && isSelected;
                    return (
                    <div
                      key={example.example_id}
                      role="button"
                      tabIndex={0}
                      className={`example-card ${isSelected ? "selected" : ""}`}
                      onClick={() => void loadExample(example.example_id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          void loadExample(example.example_id);
                        }
                      }}
                      aria-busy={isLoading}
                    >
                      <div className="example-card-meta">
                        <div className="example-card-topline">
                          <span className="example-card-fault-pill">{getFaultTypeName(example.fault_type)}</span>
                        </div>
                        <span className="example-card-title">{example.task}</span>
                        <span className="example-card-id">{example.example_id}</span>
                      </div>
                      <div className="example-card-footer">
                        <span className="example-card-hint">{example.model}</span>
                        <span className="example-card-status">{isLoading ? "Loading…" : "View"}</span>
                      </div>
                    </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>

          <div className="config-panel-footer">
            {mode === "connect" && (
              <button
                type="button"
                className={`primary config-run-btn ${running ? "is-running" : ""}`}
                disabled={running || !effectiveMcpUrl.trim()}
                onClick={() => void handleRun()}
              >
                {running ? "Running comparison..." : "Run comparison"}
              </button>
            )}
            {error && (
              <p className="upload-errors" role="alert">
                {error}
              </p>
            )}
          </div>
        </section>

        <section className="config-panel-right">
          {mode === "explore" && comparison && (
            <span className="precomputed-badge precomputed-badge-standalone">Example</span>
          )}
          {running && (
            <p className="empty-state">Running clean and faulted passes...</p>
          )}
          {!running && !comparison && (
            <div className="workbench-placeholder">
              <div className="workbench-placeholder-head">
                <h4>Ready to compare</h4>
                <p>
                  Configure a run on the left, then compare trajectories here.
                </p>
              </div>
              <div className="workbench-placeholder-grid">
                <div className="workbench-placeholder-column">
                  <span className="workbench-placeholder-label">Clean run will appear here</span>
                  <div className="workbench-placeholder-node" />
                  <div className="workbench-placeholder-node" />
                  <div className="workbench-placeholder-node" />
                </div>
                <div className="workbench-placeholder-column">
                  <span className="workbench-placeholder-label">Faulted run will appear here</span>
                  <div className="workbench-placeholder-node" />
                  <div className="workbench-placeholder-node is-faulted" />
                  <div className="workbench-placeholder-node" />
                </div>
              </div>
            </div>
          )}
          {comparison && !running && (
            <ComparisonWorkbench
              comparison={comparison}
              onComparisonUpdate={setComparison}
              liveMode={mode === "connect"}
            />
          )}
        </section>
      </div>

      <DemoMcpToolsDialog open={toolsDialogOpen} onClose={() => setToolsDialogOpen(false)} />
      <FaultTypesDialog open={faultTypesDialogOpen} onClose={() => setFaultTypesDialogOpen(false)} />
      <TaskGuidanceDialog
        open={taskGuidanceDialogOpen}
        mcpSource={mcpSource}
        onClose={() => setTaskGuidanceDialogOpen(false)}
        onSelectExample={(example) => {
          setTask(example.task);
          if (example.targetToolId) {
            setTargetToolId(example.targetToolId);
          }
        }}
      />
      <ReadFirstDialog
        open={readFirstOpen}
        onClose={() => setReadFirstOpen(false)}
        onSelectDefault={applyDefaultTask}
      />
    </div>
  );
}
