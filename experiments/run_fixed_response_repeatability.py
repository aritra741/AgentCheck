"""Fixed-response repeatability — same cached tool responses, repeated runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.common import init_experiment, run_scenarios, save_json
from agentcheck.metrics import run_consistency_report
from agentcheck.parallel import default_workers
from agentcheck.scenarios import load_all_scenarios, select_stratified_subset


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fixed-response repeatability")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/fixed_response_repeatability"),
    )
    parser.add_argument("--agent-id", default="agent-1")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument(
        "--judge-model",
        default="claude-haiku-4-5-20251001",
        help="Judge model (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--judge",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run LLM judge scoring (default: on; required for recovery-action agreement)",
    )
    parser.add_argument("--model", default=None, help="Override agent model name")
    parser.add_argument("--provider", default=None, help="Override provider")
    parser.add_argument("--base-url", default=None, help="Override API base URL")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Parallel workers (default: {default_workers()})",
    )
    args = parser.parse_args()

    init_experiment(args.output_dir)
    all_scenarios = load_all_scenarios()
    subset = select_stratified_subset(all_scenarios, per_fault_type=3)
    save_json(args.output_dir / "subset_scenario_ids.json", [s["scenario_id"] for s in subset])

    traces = run_scenarios(
        subset,
        args.agent_id,
        runs_per_scenario=args.runs,
        judge_model=args.judge_model,
        run_judge=args.judge,
        model_override=args.model,
        provider_override=args.provider,
        base_url_override=args.base_url,
        workers=args.workers,
    )

    report = run_consistency_report(traces)
    save_json(args.output_dir / "traces.json", traces)
    save_json(args.output_dir / "consistency_report.json", report)
    print(f"Fixed-response repeatability complete: {len(traces)} traces -> {args.output_dir}")
    print(f"Outcome agreement: {report['outcome_agreement_rate']:.1%}")
    print(f"Recovery action agreement: {report['recovery_action_agreement_rate']:.1%}")


if __name__ == "__main__":
    main()
