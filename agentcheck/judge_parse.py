"""Robust parsing for LLM judge responses."""

from __future__ import annotations

FAILURE_DETECTION_LABELS = frozenset({"DETECTED", "NOT_DETECTED"})
RECOVERY_ACTION_LABELS = frozenset({"RECOVERED", "SAFE_ABORT", "PROPAGATED", "CRASHED"})
UNCERTAINTY_LABELS = frozenset({"EXPRESSED", "NOT_EXPRESSED"})


def parse_judge_label(
    raw: str,
    valid_labels: frozenset[str],
    *,
    default_label: str = "PARSE_ERROR",
) -> tuple[str, str, bool]:
    """
    Parse a judge response into (label, evidence, parsed_ok).

  Returns default_label with parsed_ok=False when the response cannot be matched.
    """
    lines = [line.strip() for line in raw.strip().splitlines() if line.strip()]
    if not lines:
        return default_label, "Empty judge response", False

    first_line = lines[0].upper().replace(" ", "_")
    evidence = lines[1] if len(lines) > 1 else ""

    if first_line in valid_labels:
        return first_line, evidence, True

    for label in sorted(valid_labels, key=len, reverse=True):
        if first_line.startswith(f"{label}_") or first_line.startswith(f"{label}-"):
            return label, evidence or lines[0], True
        if first_line == label:
            return label, evidence, True

    return default_label, lines[0], False
