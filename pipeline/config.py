"""Configuration for fault types, domains, and generation assignments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FAULT_TYPES = [
    "A1",
    "A2",
    "A3",
    "A4",
    "B1",
    "B2",
    "B3",
    "B4",
    "C1",
    "C2",
    "C3",
    "C4",
]

DOMAINS = [
    "finance",
    "science_health",
    "geography_politics",
    "code_technical",
    "general_knowledge",
]

FAULT_CATEGORY_BY_TYPE = {
    "A1": "tool_execution",
    "A2": "tool_execution",
    "A3": "tool_execution",
    "A4": "tool_execution",
    "B1": "data_quality",
    "B2": "data_quality",
    "B3": "data_quality",
    "B4": "data_quality",
    "C1": "security",
    "C2": "security",
    "C3": "security",
    "C4": "security",
}

MAX_VALIDATION_RETRIES = 3
MAX_REVIEW_RETRIES = 2

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_schema_path() -> Path:
    """Resolve the bundled schema file, packaged inside agentcheck/data."""
    packaged = PROJECT_ROOT / "agentcheck" / "data" / "schema" / "scenario_template.schema.json"
    if packaged.is_file():
        return packaged
    # Fallback for editable/dev checkouts predating the packaged data layout.
    return PROJECT_ROOT / "schema" / "scenario_template.schema.json"


SCHEMA_PATH = _default_schema_path()
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "templates"
DEFAULT_REPORT_PATH = DEFAULT_OUTPUT_DIR / "_generation_report.json"


@dataclass(frozen=True)
class TemplateAssignment:
    fault_type: str
    domain: str
    variant: int


def build_assignments(
    fault_type_filter: list[str] | None = None,
    max_variants: int = 3,
    variant_start: int = 1,
) -> list[TemplateAssignment]:
    """Build generation assignments.

    Args:
        fault_type_filter: Restrict to these fault types (default: all).
        max_variants: Total number of variants desired per fault type.
        variant_start: First variant index to include (1-based).
            Use variant_start=4 with max_variants=10 to generate only variants 4-10.
    """
    assignments: list[TemplateAssignment] = []
    for i, fault_type in enumerate(FAULT_TYPES):
        if fault_type_filter and fault_type not in fault_type_filter:
            continue
        for j in range(variant_start - 1, max_variants):
            domain = DOMAINS[(i + j) % len(DOMAINS)]
            assignments.append(
                TemplateAssignment(fault_type=fault_type, domain=domain, variant=j + 1)
            )
    return assignments
