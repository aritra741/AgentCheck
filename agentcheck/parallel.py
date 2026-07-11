"""Parallel execution helpers for scenario evaluation."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TypeVar

from agentcheck.agents import Agent

T = TypeVar("T")
R = TypeVar("R")

_thread_local = threading.local()


def default_workers() -> int:
    """Default pool size for I/O-bound LLM calls."""
    env = os.environ.get("AGENTCHECK_WORKERS")
    if env:
        return max(1, int(env))
    return min(8, (os.cpu_count() or 4))


@dataclass(frozen=True)
class ScenarioRunJob:
    scenario: dict
    run_number: int


def _get_thread_agent(agent_factory: Callable[[], Agent]) -> Agent:
    agent = getattr(_thread_local, "agent", None)
    if agent is None:
        agent = agent_factory()
        _thread_local.agent = agent
    return agent


def _init_worker(agent_factory: Callable[[], Agent]) -> None:
    _thread_local.agent = agent_factory()


def run_parallel_ordered(
    items: list[T],
    fn: Callable[[T], R],
    *,
    max_workers: int = 1,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[R]:
    """Run ``fn`` on each item; return results in input order."""
    if max_workers <= 1 or len(items) <= 1:
        results = [fn(item) for item in items]
        if on_progress is not None:
            for i in range(1, len(items) + 1):
                on_progress(i, len(items))
        return results

    results: list[R | None] = [None] * len(items)
    completed = 0
    progress_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(fn, item): index for index, item in enumerate(items)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            results[index] = future.result()
            if on_progress is not None:
                with progress_lock:
                    completed += 1
                    on_progress(completed, len(items))

    return results  # type: ignore[return-value]


def run_parallel_with_agent(
    items: list[T],
    agent_factory: Callable[[], Agent],
    fn: Callable[[T, Agent], R],
    *,
    max_workers: int = 1,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[R]:
    """
    Like ``run_parallel_ordered``, but each worker thread reuses one agent instance.
    """
    if max_workers <= 1 or len(items) <= 1:
        agent = agent_factory()
        results = [fn(item, agent) for item in items]
        if on_progress is not None:
            for i in range(1, len(items) + 1):
                on_progress(i, len(items))
        return results

    def worker(item: T) -> R:
        return fn(item, _get_thread_agent(agent_factory))

    results: list[R | None] = [None] * len(items)
    completed = 0
    progress_lock = threading.Lock()

    with ThreadPoolExecutor(
        max_workers=max_workers,
        initializer=_init_worker,
        initargs=(agent_factory,),
    ) as executor:
        future_to_index = {
            executor.submit(worker, item): index for index, item in enumerate(items)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            results[index] = future.result()
            if on_progress is not None:
                with progress_lock:
                    completed += 1
                    on_progress(completed, len(items))

    return results  # type: ignore[return-value]
