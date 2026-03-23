from __future__ import annotations

import os
from typing import Any


def reasoning_enabled(*, flag: bool = False) -> bool:
    if flag:
        return True
    env = os.getenv("TRACECORE_ENABLE_REASONING_BENCHMARK", "")
    return env.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_text(value: Any) -> str | None:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _coerce_criteria(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    criteria: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        criterion_id = _coerce_text(item.get("id"))
        description = _coerce_text(item.get("description"))
        weight = item.get("weight", 1.0)
        if criterion_id and description and isinstance(weight, (int, float)):
            criteria.append({
                "id": criterion_id,
                "description": description,
                "weight": float(weight),
            })
    return criteria


def build_reasoning_benchmark(
    *,
    enabled: bool,
    task: dict[str, Any],
    agent: Any,
    action_trace: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not enabled:
        return None

    rubric = getattr(agent, "reasoning_rubric", None)
    if rubric is None and isinstance(task, dict):
        rubric = task.get("reasoning_rubric")

    rubric_id = None
    rubric_version = None
    criteria: list[dict[str, Any]] = []
    if isinstance(rubric, dict):
        rubric_id = _coerce_text(rubric.get("id"))
        rubric_version = rubric.get("version") if isinstance(rubric.get("version"), int) else None
        criteria = _coerce_criteria(rubric.get("criteria"))

    provider = _coerce_text(getattr(agent, "reasoning_judge_provider", None)) or "manual"
    adapter = _coerce_text(getattr(agent, "reasoning_judge_adapter", None)) or "none"
    summary = _coerce_text(getattr(agent, "reasoning_judge_summary", None)) or "hook_enabled"

    return {
        "enabled": True,
        "judge": {
            "adapter": adapter,
            "provider": provider,
            "mode": "feature_flag",
        },
        "rubric": {
            "id": rubric_id,
            "version": rubric_version,
            "criteria": criteria,
        },
        "trace_summary": {
            "steps_observed": len(action_trace),
            "has_llm_trace": any(bool(entry.get("llm_trace")) for entry in action_trace),
        },
        "result": {
            "status": "not_evaluated",
            "summary": summary,
            "score": None,
            "pass": None,
            "reason": None,
        },
    }
