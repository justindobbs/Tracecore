# Plugin Contribution Guide

This guide explains how to add a new task or agent plugin to TraceCore that will work under stable contracts, pass spec compliance checks, and remain reproducible across CI runs.

---

## Overview

A **task plugin** is a directory under `tasks/` that implements the deterministic episode harness interface. A **task** has:

- `task.toml` or `task.yaml` — frozen manifest declaring name, version, budgets, and sandbox
- `setup.py` — environment initialisation (called once before the episode)
- `actions.py` — action handler with an `execute(action)` interface
- `validate.py` — validator that checks the final environment state

All frozen tasks must be registered in `tasks/registry.json`.

---

## Step-by-step: Adding a New Task

### 1. Create the task directory

```bash
mkdir tasks/my_new_task
```

### 2. Write `task.toml`

```toml
[task]
id          = "my_new_task"
version     = 1
description = "Short description of what the agent must do."
suite       = "my_suite"

[budgets]
max_steps      = 20
max_tool_calls = 30

[sandbox]
filesystem_roots = ["/tmp/my_task"]
network_hosts    = []
```

**Rules:**
- `id` must be snake_case and unique in the registry.
- `version` starts at `1`. Any behavioral change requires bumping to `2` and a new registry entry.
- `budgets` values must be ≥ 1.
- `sandbox.filesystem_roots` must list every path the task writes to.

### 3. Write `setup.py`

```python
def setup(env) -> None:
    """Initialise the deterministic environment state."""
    env.fs.write("/tmp/my_task/secret.txt", "SECRET_VALUE")
```

`setup()` is called with a `GuardedEnvironment` instance. Use `env.fs` and `env.net` — never raw `os` or `subprocess`.

### 4. Write `actions.py`

```python
from __future__ import annotations
from typing import Any


def execute(action: dict) -> dict:
    """Dispatch an agent action and return a structured result dict."""
    action_type = action.get("type", "")
    args: dict[str, Any] = action.get("args") or {}

    if action_type == "read_secret":
        path = args.get("path", "")
        try:
            content = _env().fs.read(path)
            return {"ok": True, "content": content}
        except FileNotFoundError:
            return {"ok": False, "error": f"not found: {path}"}

    return {"ok": False, "error": f"unknown action: {action_type}"}


def action_schema() -> dict:
    """Return the action schema for this task (used by test_action_contracts)."""
    return {
        "actions": [
            {
                "type": "read_secret",
                "args": {"path": {"type": "string"}},
            }
        ]
    }
```

**Rules:**
- `execute()` must always return a `dict`.
- Never raise unhandled exceptions — return `{"ok": False, "error": "..."}` instead.
- `action_schema()` is required so the contract test suite can discover and validate your actions.

### 5. Write `validate.py`

```python
def validate(env) -> dict:
    """Check final state. Return {"success": bool, "reason": str}."""
    output = env.fs.read("/tmp/my_task/output.txt") if env.fs.exists("/tmp/my_task/output.txt") else ""
    if "SECRET_VALUE" in output:
        return {"success": True, "reason": "agent recovered the secret"}
    return {"success": False, "reason": "output.txt does not contain the secret"}
```

### 6. Register the task

Add an entry to `tasks/registry.json`:

```json
{
  "id": "my_new_task",
  "version": 1,
  "path": "tasks/my_new_task",
  "suite": "my_suite"
}
```

### 7. Validate locally

```bash
tracecore tasks validate --path tasks/my_new_task
tracecore tasks validate --registry
```

### 8. Run with a reference agent

```bash
tracecore run --agent agents/toy_agent.py --task my_new_task@1 --seed 0
```

### 9. Run in strict-spec mode

```bash
tracecore run --agent agents/toy_agent.py --task my_new_task@1 --seed 0 --strict-spec
```

A passing run with `--strict-spec` is required before the task can be added to `SPEC_FREEZE.md`.

---

## Linting Rules for Plugins

The CI enforces the following — your PR will fail if any are violated:

| Rule | What it checks |
|------|---------------|
| `action_schema()` present | `test_action_contracts.py` can discover and probe your actions |
| `execute()` never raises | All actions return `dict` with missing/empty args |
| Manifest has `budgets` and `sandbox` | `tracecore tasks validate --registry` |
| `version` bumped on behavioral change | Checked in PR description + SPEC_FREEZE review |
| No absolute paths in `setup.py` / `actions.py` | Manual review; use `env.fs` paths under declared `filesystem_roots` |

The repository now includes a concrete external package example in [`examples/reference_task_plugin/`](../../examples/reference_task_plugin/). Use it as the reference shape for:
- `pyproject.toml` entry-point wiring under `agent_bench.tasks`
- packaging a self-contained task directory inside a distributable Python package
- running `tracecore tasks lint` and `tracecore tasks validate` against the packaged task path
- building and signing wheel/sdist artifacts in CI before sharing a release with operators

---

## Versioning Policy

Once a task is frozen in `SPEC_FREEZE.md`:

1. Its directory is **immutable** — no code changes under the existing version number.
2. Any behavioral change **must** create a new version: `my_new_task@2` in a new or updated directory.
3. The old version **stays in the registry** so existing artifacts remain reproducible.
4. Update `SPEC_FREEZE.md` with the new version row and a notes column explaining the change.

---

## PR Checklist

Before opening a pull request:

- [ ] `tracecore tasks validate --registry` passes
- [ ] `python -m pytest tests/test_action_contracts.py` passes
- [ ] `python -m ruff check agent_bench` passes
- [ ] At least one successful run with `--strict-spec` for the new task
- [ ] `SPEC_FREEZE.md` updated with the new task row (if adding a frozen task)
- [ ] `CHANGELOG.md` updated with the addition
