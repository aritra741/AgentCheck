"""Token usage tracking for experiment cost accounting."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class UsageRecord:
    component: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class UsageTracker:
    records: list[UsageRecord] = field(default_factory=list)

    def add(
        self,
        component: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        total = prompt_tokens + completion_tokens
        self.records.append(
            UsageRecord(
                component=component,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
            )
        )

    def summary(self) -> dict:
        totals = {
            "prompt_tokens": sum(r.prompt_tokens for r in self.records),
            "completion_tokens": sum(r.completion_tokens for r in self.records),
            "total_tokens": sum(r.total_tokens for r in self.records),
        }
        by_component: dict[str, dict[str, int]] = {}
        for record in self.records:
            bucket = by_component.setdefault(
                record.component,
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            )
            bucket["prompt_tokens"] += record.prompt_tokens
            bucket["completion_tokens"] += record.completion_tokens
            bucket["total_tokens"] += record.total_tokens
        return {"totals": totals, "by_component": by_component, "calls": len(self.records)}


import threading as _threading

_thread_local_tracker = _threading.local()


def get_tracker() -> UsageTracker | None:
    return getattr(_thread_local_tracker, "active", None)


@contextmanager
def track_usage() -> Iterator[UsageTracker]:
    tracker = UsageTracker()
    previous = getattr(_thread_local_tracker, "active", None)
    _thread_local_tracker.active = tracker
    try:
        yield tracker
    finally:
        _thread_local_tracker.active = previous


def record_llm_usage(
    component: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    active = getattr(_thread_local_tracker, "active", None)
    if active is not None:
        active.add(component, model, prompt_tokens, completion_tokens)
