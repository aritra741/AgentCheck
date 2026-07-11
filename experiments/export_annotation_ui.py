"""Export the human annotation UI used for scorer alignment."""

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
from agentcheck.annotation_ui import export_annotation_html
from agentcheck.irr import export_annotation_spreadsheet, load_annotations_and_score
from agentcheck.scenarios import load_all_scenarios

_DEFAULT_HTML = Path("experiments/annotation_ui.html")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export or score the annotation UI")
    parser.add_argument(
        "--traces",
        type=Path,
        default=Path("results/injection_validation/traces.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments"),
        help="Directory for spreadsheet / judged-trace outputs",
    )
    parser.add_argument(
        "--html-path",
        type=Path,
        default=_DEFAULT_HTML,
        help="Path for the self-contained HTML annotator",
    )
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument(
        "--score",
        action="store_true",
        help="Score completed annotations CSV instead of exporting",
    )
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="Run LLM judge on traces before scoring (saves judged traces)",
    )
    parser.add_argument(
        "--judge-model",
        default="claude-haiku-4-5-20251001",
        help="Judge model for --rescore (default: Claude 4.5 Haiku)",
    )
    parser.add_argument(
        "--judge-provider",
        default=None,
        help="Judge provider (default: inferred from model, e.g. anthropic for claude-*)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel workers for --rescore",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("experiments/annotation_spreadsheet.csv"),
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Also export interactive HTML annotator",
    )
    parser.add_argument(
        "--html-only",
        action="store_true",
        help="Export only the HTML annotator (skip CSV spreadsheet)",
    )
    args = parser.parse_args()

    init_experiment(args.output_dir)
    traces = load_traces(args.traces)

    if args.rescore:
        scenarios = {
            s["scenario_id"]: s for s in load_all_scenarios()
        }
        rescored = [
            runs[0]
            for runs in rescore_traces_multiple(
                traces,
                scenarios,
                passes=1,
                judge_model=args.judge_model,
                judge_provider=args.judge_provider,
                workers=args.workers,
            )
        ]
        judged_path = args.output_dir / "traces_judged.json"
        save_json(judged_path, rescored)
        print(f"Judged traces -> {judged_path}")
        traces = rescored

    if args.score:
        report = load_annotations_and_score(args.annotations, traces)
        save_json(args.output_dir / "human_alignment_report.json", report)
        print(f"Human alignment report -> {args.output_dir / 'human_alignment_report.json'}")
        return

    if args.html_only:
        html_path = export_annotation_html(
            traces,
            args.html_path,
            sample_size=args.sample_size,
            annotator_id="annotator1",
        )
        print(f"Annotation UI -> {html_path}")
        print("Open in a browser, annotate, then click Download CSV.")
        return

    csv_path = export_annotation_spreadsheet(
        traces,
        args.output_dir / "annotation_spreadsheet.csv",
        sample_size=args.sample_size,
    )
    if args.html:
        html_path = export_annotation_html(
            traces,
            args.html_path,
            sample_size=args.sample_size,
            annotator_id="annotator1",
        )
        print(f"Annotation spreadsheet exported -> {csv_path}")
        print(f"Annotation UI -> {html_path}")
        print("Open the HTML file in a browser for easier labeling, then Download CSV.")
        return

    print(f"Annotation spreadsheet exported -> {csv_path}")
    print("Fill annotator columns, then re-run with --score")
    print("Tip: add --html-only to generate the browser annotator instead.")


if __name__ == "__main__":
    main()
