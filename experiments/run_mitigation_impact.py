"""Mitigation impact — re-run scenarios with mitigation configs enabled."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.common import init_experiment, run_scenarios, save_json
from agentcheck.agent_factory import MITIGATION_SPECS
from agentcheck.metrics import mitigation_effect_table
from agentcheck.parallel import default_workers
from agentcheck.scenarios import load_all_scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-id", default="agent-3", help="Agent to evaluate (default: agent-3)")
    parser.add_argument(
        "--mitigations",
        nargs="+",
        default=list(MITIGATION_SPECS.keys()),
        choices=list(MITIGATION_SPECS.keys()),
    )
    parser.add_argument("--workers", type=int, default=default_workers())
    parser.add_argument("--judge", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--judge-model",
        default="claude-haiku-4-5-20251001",
        help="Judge model (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results/mitigation_impact"))
    args = parser.parse_args()

    init_experiment(args.output_dir)
    scenarios = load_all_scenarios()
    traces_by_config: dict[str, list] = {}

    for mitigation_id in args.mitigations:
        print(f"Running mitigation config: {mitigation_id}", flush=True)
        traces = run_scenarios(
            scenarios,
            args.agent_id,
            mitigation_id=mitigation_id,
            workers=args.workers,
            judge_model=args.judge_model,
            run_judge=args.judge,
        )
        traces_by_config[mitigation_id] = traces
        save_json(args.output_dir / f"traces_{mitigation_id}.json", traces)

    summary = mitigation_effect_table(traces_by_config)
    summary["agent_id"] = args.agent_id
    save_json(args.output_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
