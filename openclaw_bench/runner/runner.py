"""Main execution loop."""

from __future__ import annotations

import inspect

from openclaw_bench.agent.loader import load_agent
from openclaw_bench.env.environment import Environment
from openclaw_bench.runner.budgets import Budgets
from openclaw_bench.runner.results import make_result
from openclaw_bench.tasks.loader import load_task


def _parse_task_ref(task_ref: str) -> tuple[str, int | None]:
    if "@" in task_ref:
        task_id, version = task_ref.split("@", 1)
        return task_id, int(version)
    return task_ref, None


def _action_schema(actions_mod) -> dict[str, list[str]]:
    schema: dict[str, list[str]] = {}
    for name, fn in inspect.getmembers(actions_mod, inspect.isfunction):
        if name.startswith("_") or name == "set_env":
            continue
        params = [p.name for p in inspect.signature(fn).parameters.values()]
        schema[name] = params
    return schema


def _validate_action(action: dict, schema: dict[str, list[str]]) -> tuple[bool, str | None]:
    if not isinstance(action, dict):
        return False, "action_must_be_dict"
    action_type = action.get("type")
    args = action.get("args")
    if not action_type or not isinstance(action_type, str):
        return False, "invalid_action_type"
    if action_type not in schema:
        return False, "unknown_action"
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return False, "args_must_be_dict"
    required = schema[action_type]
    for key in required:
        if key not in args:
            return False, "missing_arg"
    return True, None


def run(agent_path: str, task_ref: str, seed: int = 0) -> dict:
    task_id, version = _parse_task_ref(task_ref)
    task = load_task(task_id, version)

    env = Environment()
    task["setup"].setup(seed, env)

    actions_mod = task["actions"]
    if hasattr(actions_mod, "set_env"):
        actions_mod.set_env(env)

    agent = load_agent(agent_path)
    budgets = task["default_budget"]
    max_steps = int(budgets.get("steps", 0))
    max_tool_calls = int(budgets.get("tool_calls", 0))
    budget = Budgets(max_steps, max_tool_calls)

    schema = _action_schema(actions_mod)

    task_spec = {
        "id": task["id"],
        "description": task["description"],
        "budgets": budgets,
        "actions": schema,
    }
    agent.reset(task_spec)

    last_action = None
    last_result = None
    action_trace = []

    while True:
        if budget.timed_out():
            return make_result(
                task_id=task["id"],
                version=task["version"],
                seed=seed,
                success=False,
                failure_reason="timeout",
                steps_used=max_steps - budget.steps_remaining,
                tool_calls_used=max_tool_calls - budget.tool_calls_remaining,
                action_trace=action_trace,
            )

        if budget.steps_remaining <= 0:
            return make_result(
                task_id=task["id"],
                version=task["version"],
                seed=seed,
                success=False,
                failure_reason="steps_exhausted",
                steps_used=max_steps,
                tool_calls_used=max_tool_calls - budget.tool_calls_remaining,
                action_trace=action_trace,
            )

        observation = {
            "step": max_steps - budget.steps_remaining + 1,
            "task": {"id": task["id"], "description": task["description"]},
            "last_action": last_action,
            "last_action_result": last_result,
            "visible_state": env.visible_state(),
            "budget_remaining": {
                "steps": budget.steps_remaining,
                "tool_calls": budget.tool_calls_remaining,
            },
        }

        agent.observe(observation)
        action = agent.act()

        budget.consume_step()
        ok, reason = _validate_action(action, schema)
        if not ok:
            return make_result(
                task_id=task["id"],
                version=task["version"],
                seed=seed,
                success=False,
                failure_reason=reason,
                steps_used=max_steps - budget.steps_remaining,
                tool_calls_used=max_tool_calls - budget.tool_calls_remaining,
                action_trace=action_trace,
            )

        if budget.tool_calls_remaining <= 0:
            return make_result(
                task_id=task["id"],
                version=task["version"],
                seed=seed,
                success=False,
                failure_reason="tool_calls_exhausted",
                steps_used=max_steps - budget.steps_remaining,
                tool_calls_used=max_tool_calls,
                action_trace=action_trace,
            )

        action_type = action["type"]
        args = action.get("args", {}) or {}
        try:
            result = getattr(actions_mod, action_type)(**args)
        except Exception as exc:  # pragma: no cover - defensive
            return make_result(
                task_id=task["id"],
                version=task["version"],
                seed=seed,
                success=False,
                failure_reason=f"action_exception:{exc}",
                steps_used=max_steps - budget.steps_remaining,
                tool_calls_used=max_tool_calls - budget.tool_calls_remaining,
                action_trace=action_trace,
            )

        budget.consume_tool_call()

        if action_type == "list_dir" and isinstance(result, dict) and result.get("ok"):
            env.mark_seen(result.get("files", []))

        action_trace.append({"step": observation["step"], "action": action, "result": result})
        last_action = action
        last_result = result

        if budget.tool_calls_remaining < 0:
            return make_result(
                task_id=task["id"],
                version=task["version"],
                seed=seed,
                success=False,
                failure_reason="tool_calls_exhausted",
                steps_used=max_steps - budget.steps_remaining,
                tool_calls_used=max_tool_calls,
                action_trace=action_trace,
            )

        validation = task["validate"].validate(env)
        if validation.get("ok"):
            return make_result(
                task_id=task["id"],
                version=task["version"],
                seed=seed,
                success=True,
                failure_reason=None,
                steps_used=max_steps - budget.steps_remaining,
                tool_calls_used=max_tool_calls - budget.tool_calls_remaining,
                action_trace=action_trace,
            )
