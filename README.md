# AgentCheck

Code and artifacts for **AgentCheck: A Reproduce–Intervene–Mitigate Workbench for LLM Agents over MCP**.

AgentCheck connects to an MCP server (or uses bundled examples), runs a clean agent execution, replays the same run while injecting exactly one tool-response fault, scores how the agent handled the fault, and optionally re-runs with mitigations to confirm whether a fix closes the failure.

## Layout

- `agentcheck/` — comparison engine, fault injection, deterministic pass/fail scoring, LLM-judge diagnostics
- `dashboard/` — FastAPI backend + React frontend
- `agent_specs/` — bundled example specs
- `templates/` — 120-scenario suite
- `experiments/` — experiment runners + annotation UI
- `results/` — experiment outputs
- `dashboard/seed/agentcheck.db` — precomputed comparisons for **Explore examples**

## Setup

```bash
cd AgentCheck
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r dashboard/requirements.txt
cp .env.example .env
# Edit .env — see that file for workbench keys and multi-model experiment keys
```

Frontend (development mode):

```bash
cd dashboard/frontend
npm install
```

## Running the workbench

### Development

Terminal 1 — backend:

```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn dashboard.api.main:app --reload --port 8000
```

Terminal 2 — frontend:

```bash
cd dashboard/frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

### Single-server

```bash
source .venv/bin/activate
PYTHONPATH=. uvicorn dashboard.api.main:app --port 8000
```

Open [http://localhost:8000](http://localhost:8000). **Explore examples** works from the seed database without API keys.

## Experiments and results

| Results dir | Study |
|-------------|-------|
| `results/injection_validation/` | Injection validation |
| `results/fixed_response_repeatability/` | Fixed-response repeatability |
| `results/judge_repeatability/` | Judge repeatability |
| `results/comparative_profiling/` | Comparative agent profiling |
| `results/mitigation_impact/` | Mitigation impact |

The suite is **120** scenarios (10 per fault type). Experiment runners use `evaluate.py` (MCP comparison → deterministic fault-handling checks → optional LLM judge). Summaries live in each results directory as `summary.json`.

### Annotation UI

Self-contained HTML annotator (no server):

```bash
open experiments/annotation_ui.html
```

Regenerate from injection-validation traces:

```bash
python experiments/export_annotation_ui.py --html-only
```

### Re-run experiments

Requires API keys (see `.env.example`). Comparative profiling and mitigation impact need keys for every agent you run:

```bash
python experiments/run_injection_validation.py
python experiments/run_fixed_response_repeatability.py
python experiments/run_judge_repeatability.py
python experiments/run_comparative_profiling.py
python experiments/run_mitigation_impact.py
```

Default judge model is `claude-haiku-4-5-20251001`. Use `--no-judge` for deterministic pass/fail without diagnostic labels.

## Environment variables

Copy `.env.example` to `.env` and fill in keys. Live workbench runs need `OPENAI_API_KEY` (agent) and `ANTHROPIC_API_KEY` (Claude judge). Multi-agent experiment re-runs also need provider keys for Gemini, DeepSeek, and Llama — see `.env.example`.

## License

MIT — see [LICENSE](LICENSE).
