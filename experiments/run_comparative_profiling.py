"""Comparative agent profiling — five agents × 120 scenarios."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.common import init_experiment, run_scenarios, save_json
from agentcheck.agent_factory import AGENT_SPECS
from agentcheck.metrics import (
    agent_summary_metrics,
    category_pass_rates,
    divergence_examples,
    pass_rate_matrix,
)
from agentcheck.parallel import default_workers
from agentcheck.rate_limit import default_rate_limit_retries
from agentcheck.scenarios import load_all_scenarios

DEFAULT_AGENT_IDS = [
    "agent-1-zero-shot",
    "agent-1",
    "agent-2",
    "agent-3",
    "agent-4-react",
]


def _resolve_agent_ids(args: argparse.Namespace) -> list[str]:
    if args.agent and args.agents:
        raise SystemExit("Use only one of --agent or --agents, not both.")
    if args.agent:
        return [args.agent]
    if args.agents:
        return args.agents
    return DEFAULT_AGENT_IDS.copy()


def build_summary(
    all_traces: list[dict],
    agent_ids: list[str],
    *,
    include_judge_metrics: bool,
    judge_model: str | None = None,
) -> dict:
    summary = {
        "agents_run": agent_ids,
        "pass_rate_matrix": pass_rate_matrix(all_traces, agent_ids=agent_ids),
        "category_pass_rates": category_pass_rates(all_traces),
        "divergence_examples": divergence_examples(all_traces, limit=4),
    }
    if judge_model:
        summary["judge_model"] = judge_model
    if include_judge_metrics:
        summary["agent_summaries"] = agent_summary_metrics(all_traces)
    return summary


def main() -> None:
    valid_agents = list(AGENT_SPECS.keys())
    parser = argparse.ArgumentParser(description="Run comparative agent profiling")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/comparative_profiling"),
    )
    parser.add_argument(
        "--judge-model",
        default="claude-haiku-4-5-20251001",
        help="Judge model (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--judge",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run LLM judge scoring (default: on; required for Prop./Sec.P. metrics)",
    )
    parser.add_argument(
        "--agent",
        metavar="ID",
        choices=valid_agents,
        help="Run a single agent only (e.g. agent-1). Shorthand for --agents agent-1",
    )
    parser.add_argument(
        "--agents",
        nargs="+",
        choices=valid_agents,
        help="One or more agent IDs to run (default: all 5)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override model for all selected agents",
    )
    parser.add_argument("--provider", default=None, help="Override provider")
    parser.add_argument("--base-url", default=None, help="Override API base URL")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            f"Parallel scenario workers per agent (default: {default_workers()}, "
            "or AGENTCHECK_WORKERS env). Retries automatically on HTTP 429."
        ),
    )
    parser.add_argument(
        "--rate-limit-retries",
        type=int,
        default=None,
        help=(
            f"Max retries per scenario when the API returns 429 "
            f"(default: {default_rate_limit_retries()}, or AGENTCHECK_RATE_LIMIT_RETRIES env)"
        ),
    )
    args = parser.parse_args()

    agent_ids = _resolve_agent_ids(args)
    init_experiment(args.output_dir)
    scenarios = load_all_scenarios()
    all_traces: list[dict] = []

    print(
        f"Running {len(agent_ids)} agent(s) × {len(scenarios)} scenarios "
        f"with {args.workers or default_workers()} parallel workers"
    )

    for agent_id in agent_ids:
        print(f"Running agent {agent_id}...")
        traces = run_scenarios(
            scenarios,
            agent_id,
            runs_per_scenario=1,
            judge_model=args.judge_model,
            run_judge=args.judge,
            model_override=args.model,
            provider_override=args.provider,
            base_url_override=args.base_url,
            workers=args.workers,
            rate_limit_retries=args.rate_limit_retries,
        )
        all_traces.extend(traces)
        save_json(args.output_dir / f"traces_{agent_id}.json", traces)

    summary = build_summary(
        all_traces,
        agent_ids,
        include_judge_metrics=args.judge,
        judge_model=args.judge_model if args.judge else None,
    )
    save_json(args.output_dir / "traces_all.json", all_traces)
    save_json(args.output_dir / "summary.json", summary)

    print(f"Comparative profiling complete: {len(all_traces)} traces -> {args.output_dir}")
    categories = summary["category_pass_rates"]
    for agent_id in agent_ids:
        print(f"  {agent_id} overall: {categories.get(agent_id, {}).get('overall', 'N/A')}")


if __name__ == "__main__":
    main()
