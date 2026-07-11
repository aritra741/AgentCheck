"""Injection validation — confirm faults land and agents engage (120 scenarios)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agentcheck.metrics import injection_validation_report
from agentcheck.parallel import default_workers
from agentcheck.scenarios import load_all_scenarios
from experiments.common import init_experiment, run_scenarios, save_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run injection validation")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/injection_validation"),
    )
    parser.add_argument("--agent-id", default="agent-1")
    parser.add_argument(
        "--judge-model",
        default="claude-haiku-4-5-20251001",
        help="Judge model when --judge is set (default matches other experiment runners)",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Run LLM judge scoring (off by default)",
    )
    parser.add_argument("--model", default=None, help="Override agent model name")
    parser.add_argument(
        "--provider",
        default=None,
        help="Override provider (openai/deepseek/openai_compatible)",
    )
    parser.add_argument("--base-url", default=None, help="Override API base URL")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Parallel workers (default: {default_workers()}, or AGENTCHECK_WORKERS env)",
    )
    args = parser.parse_args()

    init_experiment(args.output_dir)
    scenarios = load_all_scenarios()
    traces = run_scenarios(
        scenarios,
        args.agent_id,
        runs_per_scenario=1,
        judge_model=args.judge_model,
        run_judge=args.judge,
        model_override=args.model,
        provider_override=args.provider,
        base_url_override=args.base_url,
        workers=args.workers,
    )

    report = injection_validation_report(traces)
    save_json(args.output_dir / "traces.json", traces)
    save_json(args.output_dir / "injection_validation.json", report)
    print(f"Injection validation complete: {len(traces)} traces -> {args.output_dir}")
    print(f"Injection success rate: {report['overall']['injection_success_rate']:.1%}")
    print(f"Agent engagement rate: {report['overall']['agent_engagement_rate']:.1%}")


if __name__ == "__main__":
    main()
