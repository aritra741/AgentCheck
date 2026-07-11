"""Generate paper figures from experiment summary data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FAULT_ORDER = ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "C4"]
AGENT_ORDER = ["agent-1-zero-shot", "agent-1", "agent-2", "agent-3", "agent-4-react"]
AGENT_DISPLAY = {
    "agent-1-zero-shot": "agent-1-zs",
    "agent-1": "agent-1",
    "agent-2": "agent-2",
    "agent-3": "agent-3",
    "agent-4-react": "agent-4",
}


def _save_figure(fig: Any, output_path: Path, *, dpi: int = 200) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    if output_path.suffix.lower() != ".png":
        fig.savefig(output_path.with_suffix(".png"), dpi=dpi)
    return output_path


def generate_pass_rate_heatmap(
    matrix: dict[str, dict[str, str]],
    output_path: Path,
    *,
    title: str = "Pass Rate by Agent and Fault Type",
) -> Path:
    """Figure 1: 4×12 heatmap of pass counts out of 10."""
    import matplotlib.pyplot as plt
    import numpy as np

    ordered_agents = [agent for agent in AGENT_ORDER if agent in matrix]
    ordered_agents.extend(sorted(agent for agent in matrix if agent not in AGENT_ORDER))
    agents = ordered_agents
    data = np.zeros((len(agents), len(FAULT_ORDER)))
    annotations = []

    for i, agent in enumerate(agents):
        row_ann = []
        for j, fault in enumerate(FAULT_ORDER):
            cell = matrix.get(agent, {}).get(fault, "0/0")
            passed, total = _parse_cell(cell)
            rate = passed / total if total else 0
            data[i, j] = rate
            row_ann.append(str(passed))
        annotations.append(row_ann)

    fig, ax = plt.subplots(figsize=(10.2, 3.9))
    im = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(FAULT_ORDER)))
    ax.set_xticklabels(FAULT_ORDER, fontsize=18, fontweight="bold")
    ax.set_yticks(range(len(agents)))
    ax.set_yticklabels([AGENT_DISPLAY.get(agent, agent) for agent in agents], fontsize=18)
    ax.set_title(title, fontsize=20, pad=10)
    ax.tick_params(axis="both", length=0)

    ax.set_xticks(np.arange(-0.5, len(FAULT_ORDER), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(agents), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.8)
    ax.tick_params(which="minor", bottom=False, left=False)

    for i in range(len(agents)):
        for j in range(len(FAULT_ORDER)):
            ax.text(
                j,
                i,
                annotations[i][j],
                ha="center",
                va="center",
                fontsize=20,
                fontweight="bold",
                color="#111827",
            )

    cbar = fig.colorbar(im, ax=ax, label="Pass rate")
    cbar.ax.tick_params(labelsize=15)
    cbar.set_label("Pass rate", fontsize=17)
    fig.tight_layout(pad=0.35)
    _save_figure(fig, output_path)
    plt.close(fig)
    return output_path


def generate_recovery_stacked_bar(
    summaries: dict[str, dict[str, Any]],
    output_path: Path,
    *,
    title: str = "Recovery Action Distribution by Agent",
) -> Path:
    """Figure 2: stacked bar chart of recovery actions per agent."""
    import matplotlib.pyplot as plt

    ordered_agents = [agent for agent in AGENT_ORDER if agent in summaries]
    ordered_agents.extend(sorted(agent for agent in summaries if agent not in AGENT_ORDER))
    agents = ordered_agents
    categories = ["recovered", "safe_abort", "propagated", "crashed"]
    colors = {"recovered": "#2ca02c", "safe_abort": "#1f77b4", "propagated": "#d62728", "crashed": "#7f7f7f"}

    fig, ax = plt.subplots(figsize=(8.4, 5.8))
    bottoms = [0] * len(agents)
    display_agents = [AGENT_DISPLAY.get(agent, agent) for agent in agents]

    for cat in categories:
        values = [summaries[a].get("recovery_distribution", {}).get(cat, 0) for a in agents]
        ax.bar(display_agents, values, bottom=bottoms, label=cat, color=colors[cat])
        bottoms = [b + v for b, v in zip(bottoms, values)]

    ax.set_title(title, fontsize=14)
    ax.set_ylabel("Run count", fontsize=15)
    ax.tick_params(axis="both", labelsize=13)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.legend(
        fontsize=11,
        framealpha=1,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        borderaxespad=0,
    )
    fig.tight_layout(rect=(0, 0, 0.86, 1))
    _save_figure(fig, output_path)
    plt.close(fig)
    return output_path


def generate_figures_from_summary(summary_path: Path, output_dir: Path) -> dict[str, str]:
    """Generate all figures from a summary.json produced by an experiment run."""
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    paths: dict[str, str] = {}

    if "pass_rate_matrix" in summary:
        paths["heatmap"] = str(
            generate_pass_rate_heatmap(
                summary["pass_rate_matrix"],
                output_dir / "fig1_pass_rate_heatmap.pdf",
            )
        )

    if "agent_summaries" in summary:
        paths["recovery_bar"] = str(
            generate_recovery_stacked_bar(
                summary["agent_summaries"],
                output_dir / "fig2_recovery_distribution.pdf",
            )
        )

    return paths


def _parse_cell(cell: str) -> tuple[int, int]:
    if "/" not in cell:
        return 0, 0
    a, b = cell.split("/", 1)
    return int(a), int(b)
