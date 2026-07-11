# AgentCheck

AgentCheck is an **MCP fault-injection workbench** for tool-using LLM agents.

It connects to an MCP server (or uses bundled examples), runs a clean agent execution, replays the same run while injecting exactly one tool-response fault, scores how the agent handled the fault, and optionally re-runs with mitigations to confirm whether a fix closes the failure.

## What this package includes

This distribution contains only what is needed to **run the workbench**:

- `agentcheck/`: comparison engine, fault injection, Leg A / Leg B scoring
- `dashboard/`: FastAPI backend + React frontend
- `agent_specs/`: bundled example specs (120-scenario suite)
- `dashboard/seed/agentcheck.db`: precomputed comparisons for **Explore examples**
- `pipeline/llm.py`: LLM client used by diagnostic scoring

It does **not** include paper sources, experiment runners, evaluation results, annotation data, scenario-authoring tooling, or deployment configs.

## Features

1. **Connect an MCP server**: live clean vs. faulted comparison against your own tools
2. **Explore bundled examples**: browse precomputed comparisons with no live model calls
3. **Primary pass/fail checks** (Leg A) plus **diagnostic labels** (Leg B: failure detection, recovery, uncertainty)
4. **Mitigation re-run** with `fix_confirmed` when failed checks close

## Setup

### Python

```bash
cd AgentCheck-reviewer
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r dashboard/requirements.txt
cp .env.example .env
# Edit .env and add at least one model API key for live runs
```

### Frontend (development mode)

```bash
cd dashboard/frontend
npm install
```

## Running

### Development (recommended)

Terminal 1 (backend):

```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn dashboard.api.main:app --reload --port 8000
```

Terminal 2 (frontend):

```bash
cd dashboard/frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

### Single-server (uses prebuilt `dashboard/frontend/dist` if present)

```bash
source .venv/bin/activate
# Optional: rebuild the UI
# cd dashboard/frontend && npm install && npm run build && cd ../..
PYTHONPATH=. uvicorn dashboard.api.main:app --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

The backend copies `dashboard/seed/agentcheck.db` into place automatically on startup so **Explore examples** works out of the box.

## Environment variables

Copy `.env.example` to `.env`. Live **Connect** runs need a provider key, for example:

```bash
OPENAI_API_KEY=...
# or OPENROUTER_API_KEY / DEEPSEEK_API_KEY / GOOGLE_API_KEY
```

**Explore examples** works from the seed database without API keys.

## API surface

| Route | Purpose |
|-------|---------|
| `POST /api/run` | Live clean / faulted / mitigated comparison |
| `GET /api/examples` | List bundled examples |
| `GET /api/examples/{id}` | Load a bundled example + precomputed comparison |
| `GET/POST /mcp` | Built-in demo MCP server |
