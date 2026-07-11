"""Scenario template loading and suite management."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.validator import ValidatorAgent


def _default_templates_dir() -> Path:
    """Resolve the bundled templates directory.

    In a repo checkout, prefer the top-level templates directory so template
    edits are reflected immediately. Fall back to the packaged data directory
    for installed builds.
    """
    repo_templates = Path(__file__).resolve().parent.parent / "templates"
    if repo_templates.is_dir():
        return repo_templates
    packaged = Path(__file__).resolve().parent / "data" / "templates"
    if packaged.is_dir():
        return packaged
    return repo_templates


_TEMPLATES_DIR = _default_templates_dir()
_validator = ValidatorAgent()


def load_scenario(
    scenario_id: str,
    templates_dir: Path | None = None,
    *,
    validate: bool = True,
) -> dict:
    """Load a scenario template JSON by scenario_id."""
    base = templates_dir or _TEMPLATES_DIR
    path = base / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario template not found: {path}")
    with path.open(encoding="utf-8") as f:
        scenario = json.load(f)

    if validate:
        errors = _validator.validate_template(scenario)
        if errors:
            joined = "\n".join(f"  - {e}" for e in errors)
            raise ValueError(f"Invalid scenario template {scenario_id}:\n{joined}")

    return normalize_scenario_metadata(scenario)


def load_all_scenarios(
    templates_dir: Path | None = None,
    *,
    validate: bool = True,
) -> list[dict]:
    """Load all scenario templates in the 120-scenario suite."""
    base = templates_dir or _TEMPLATES_DIR
    scenarios: list[dict] = []
    for path in sorted(base.glob("*.json")):
        if path.name.startswith("_"):
            continue
        scenario = load_scenario(path.stem, templates_dir=base, validate=validate)
        scenarios.append(scenario)

    _assert_suite_counts(scenarios)
    return scenarios


def normalize_scenario_metadata(scenario: dict) -> dict:
    """Ensure the template version is present in scenario metadata."""
    scenario = dict(scenario)
    metadata = dict(scenario.get("metadata", {}))
    metadata.setdefault("template_version", "1.0")
    scenario["metadata"] = metadata
    return scenario


def select_stratified_subset(
    scenarios: list[dict],
    per_fault_type: int = 3,
    *,
    seed: int = 42,
) -> list[dict]:
    """Select a random stratified subset (e.g., 36 scenarios = 3 per fault type)."""
    from collections import defaultdict
    import random

    by_fault: dict[str, list[dict]] = defaultdict(list)
    for scenario in scenarios:
        by_fault[scenario["fault_type"]].append(scenario)

    rng = random.Random(seed)
    selected: list[dict] = []
    for fault_type in sorted(by_fault):
        pool = by_fault[fault_type]
        rng.shuffle(pool)
        selected.extend(pool[:per_fault_type])
    return selected


def _assert_suite_counts(scenarios: list[dict]) -> None:
    from collections import Counter

    counts = Counter(s["fault_type"] for s in scenarios)
    if len(scenarios) != 120:
        raise ValueError(f"Official suite must have 120 scenarios, found {len(scenarios)}")
    for fault in sorted(counts):
        if counts[fault] != 10:
            raise ValueError(f"Expected 10 scenarios for {fault}, found {counts[fault]}")
