"""Judge repeatability — rescore the same fixed traces multiple times."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.common import (
    init_experiment,
    load_traces,
    rescore_traces_multiple,
    save_json,
)
from agentcheck.metrics import label_repeatability_report
from agentcheck.parallel import default_workers
from agentcheck.scenarios import load_all_scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description="Run judge repeatability")
    parser.add_argument(
        "--traces",
        type=Path,
        default=Path("results/fixed_response_repeatability/traces.json"),
        help="Traces from fixed-response repeatability (uses run 1 per scenario)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/judge_repeatability"),
    )
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--judge-model", default="claude-haiku-4-5-20251001")
    parser.add_argument(
        "--judge-provider",
        default=None,
        help="Judge provider (default: inferred from model)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=f"Parallel workers for rescoring (default: {default_workers()})",
    )
    args = parser.parse_args()

    init_experiment(args.output_dir)
    all_traces = load_traces(args.traces)

    fixed: dict[str, dict] = {}
    for trace in all_traces:
        if trace.get("run_number", 1) == 1:
            fixed[trace["scenario_id"]] = trace
    fixed_traces = list(fixed.values())

    scenarios = {s["scenario_id"]: s for s in load_all_scenarios()}
    rescored = rescore_traces_multiple(
        fixed_traces,
        scenarios,
        passes=args.passes,
        judge_model=args.judge_model,
        judge_provider=args.judge_provider,
        workers=args.workers,
    )

    report = label_repeatability_report(rescored)
    save_json(args.output_dir / "rescore_runs.json", rescored)
    save_json(args.output_dir / "repeatability_report.json", report)
    print(f"Judge repeatability complete: {len(fixed_traces)} traces × {args.passes} passes")
    print(f"Pass/fail agreement: {report.get('overall_pass_fail_agreement', 0):.1%}")
    print(f"Recovery action agreement: {report.get('recovery_action_agreement', 0):.1%}")


if __name__ == "__main__":
    main()
