---
description: Task manifest schema (v0.1)
---

# Task Manifest (v0.1)

Every task directory can include a `task.toml` manifest describing deterministic contracts, budgets, and entrypoints. The loader prefers `task.toml` when present. Legacy `task.yaml` files are still accepted for older tasks, but new work should use TOML.

## Example
```toml
id = "filesystem_hidden_config"
suite = "filesystem"
version = 1
description = "Extract the value of API_KEY from the filesystem."
deterministic = true
seed_behavior = "fixed"

[budgets]
steps = 200
tool_calls = 40

[action_surface]
source = "actions.py"
schema = "introspected"

[validator]
entrypoint = "validate.py:validate"

[setup]
entrypoint = "setup.py:setup"
```

## Required fields
- `id` (string): Unique task identifier.
- `suite` (string): Task suite label (`filesystem`, `api`, etc.).
- `version` (int): Frozen task version.
- `description` (string): Human-readable summary.
- `deterministic` (bool): Whether the task is deterministic under fixed seeds.
- `seed_behavior` (string): How the task uses the seed (`fixed`, `stochastic`, `ignored`).
- `budgets.steps` (int): Maximum steps per run.
- `budgets.tool_calls` (int): Maximum tool calls per run.
- `action_surface.source` (string): Actions module path (usually `actions.py`).
- `validator.entrypoint` (string): Validator entrypoint (usually `validate.py:validate`).

## Optional fields
- `setup.entrypoint` (string): Setup entrypoint (usually `setup.py:setup`).
- `action_surface.schema` (string): How the action surface is described (default: `introspected`).

## Compatibility
- If both `task.toml` and `task.yaml` exist, the TOML manifest wins.
- Registry entries (`tasks/registry.json` or plugin descriptors) must match the manifest `id`, `suite`, and `version`.
- Schema-breaking changes require a new task version and an update to `SPEC_FREEZE.md`.

