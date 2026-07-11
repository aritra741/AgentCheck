"""Shared helpers for experiment runners."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agentcheck.agent_factory import (
    MITIGATION_SPECS,
    create_experiment_agent,
)
from agentcheck.agents import Agent
from agentcheck.evaluate import evaluate_scenario, rescore_trace
from agentcheck.parallel import (
    ScenarioRunJob,
    default_workers,
    run_parallel_ordered,
    run_parallel_with_agent,
)
from agentcheck.rate_limit import default_rate_limit_retries, retry_on_rate_limit
from agentcheck.scenarios import load_all_scenarios, load_scenario


def init_experiment(output_dir: Path) -> None:
    load_dotenv()
    output_dir.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_traces(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _progress_printer(done: int, total: int) -> None:
    print(f"  [{done}/{total}] scenarios complete", flush=True)


def run_scenarios(
    scenarios: list[dict],
    agent_id: str,
    *,
    runs_per_scenario: int = 1,
    judge_model: str = "claude-haiku-4-5-20251001",
    judge_provider: str | None = None,
    run_judge: bool = False,
    mitigation_id: str | None = None,
    persist: bool = True,
    workers: int | None = None,
    rate_limit_retries: int | None = None,
    model_override: str | None = None,
    provider_override: str | None = None,
    base_url_override: str | None = None,
) -> list[dict]:
    mitigations = MITIGATION_SPECS.get(mitigation_id) if mitigation_id else None
    pool_size = workers if workers is not None else default_workers()
    retries = (
        rate_limit_retries
        if rate_limit_retries is not None
        else default_rate_limit_retries()
    )

    jobs = [
        ScenarioRunJob(scenario=scenario, run_number=run_num)
        for scenario in scenarios
        for run_num in range(1, runs_per_scenario + 1)
    ]

    def make_agent() -> Agent:
        return create_experiment_agent(
            agent_id,
            model_override=model_override,
            provider_override=provider_override,
            base_url_override=base_url_override,
        )

    def run_job(job: ScenarioRunJob, agent: Agent) -> dict:
        def evaluate() -> dict:
            return evaluate_scenario(
                job.scenario,
                agent,
                job.run_number,
                judge_model=judge_model,
                judge_provider=judge_provider,
                run_judge=run_judge,
                mitigations=mitigations,
                persist=persist,
            )

        if retries <= 0:
            return evaluate()
        return retry_on_rate_limit(evaluate, max_retries=retries)

    show_progress = len(jobs) > 1
    return run_parallel_with_agent(
        jobs,
        make_agent,
        run_job,
        max_workers=pool_size,
        on_progress=_progress_printer if show_progress else None,
    )


def rescore_traces_multiple(
    traces: list[dict],
    scenarios_by_id: dict[str, dict],
    *,
    passes: int = 3,
    judge_model: str = "claude-haiku-4-5-20251001",
    judge_provider: str | None = None,
    workers: int | None = None,
) -> list[list[dict]]:
    pool_size = workers if workers is not None else default_workers()

    def rescore_one(trace: dict) -> list[dict]:
        scenario = scenarios_by_id[trace["scenario_id"]]
        return [
            rescore_trace(trace, scenario, judge_model=judge_model, judge_provider=judge_provider)
            for _ in range(passes)
        ]

    return run_parallel_ordered(
        traces,
        rescore_one,
        max_workers=pool_size,
    )
