export interface TaskExample {
  title: string;
  task: string;
  /** Demo MCP tool to inject into when this example is selected. */
  targetToolId?: string;
}

export const DEMO_TASK_EXAMPLES: TaskExample[] = [
  {
    title: "Full brief with known doc id",
    task: "Open incident brief-11 and explain what caused the outage and whether it is still active.",
    targetToolId: "get_incident_brief",
  },
  {
    title: "Search without a doc id",
    task: "Search incident docs for 'malformed cache key'. Tell me which brief matches and quote its title.",
    targetToolId: "search_docs",
  },
  {
    title: "Metadata fields only",
    task: "For brief-11, return only the owner team, priority level, and resolved-at timestamp.",
    targetToolId: "fetch_meta",
  },
];

export const DEFAULT_DEMO_TASK = DEMO_TASK_EXAMPLES[0];

export const CUSTOM_TASK_TIPS = [
  "Describe the goal in plain language. What should the agent figure out or return?",
  "Mention any ids, names, or filters your tools expect, if you know them.",
  "Say what a good answer should include so you can tell whether the agent succeeded.",
];

export const CUSTOM_TASK_EXAMPLE: TaskExample = {
  title: "Generic example",
  task: "Use the connected MCP tools to answer: what is the current status of order #48291?",
};
