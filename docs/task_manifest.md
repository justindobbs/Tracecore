---
description: Task manifest schema (v0.1)
---

# Task Manifest (v0.1)

Every task directory can include a `task.toml` manifest describing deterministic contracts, budgets, and entrypoints. The loader prefers `task.toml` when present. Legacy `task.yaml` files are still accepted for older tasks, but new work should use TOML. See `docs/contract_spec.md` for the broader benchmark contract.

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

[sandbox]
filesystem_roots = ["/app"]
network_hosts = []
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
- `sandbox.filesystem_roots` (array of strings): Required for deterministic tasks. Absolute path prefixes the task may access (e.g. `"/app"`).
- `sandbox.network_hosts` (array of strings): Required for deterministic tasks. Literal or wildcard hostnames that task actions may access.

## Optional fields
- `setup.entrypoint` (string): Setup entrypoint (usually `setup.py:setup`).
- `action_surface.schema` (string): How the action surface is described (default: `introspected`).
Non-deterministic tasks may omit the `sandbox` table.

## Sandbox enforcement
- The harness enforces filesystem and network allowlists at runtime.
- Network checks accept literal hosts, wildcard domains, and IP literals; only `http`/`https` default ports are allowed.
- Record mode captures per-step IO audit entries and replays/strict enforce that the live IO trace matches the bundle.
- Bundles without sandbox declarations fail `agent-bench bundle verify` and replay/strict checks.

## Reviewer checklist
- Deterministic tasks include `[sandbox]` with both `filesystem_roots` and `network_hosts`.
- Any network access in actions is guarded via `env.require_network(host)` (or `env.network_guard().check(host)`).
- Record-mode bundle includes `manifest.json` with `sandbox` and `tool_calls.jsonl` entries with `io_audit`.

## Compatibility
- If both `task.toml` and `task.yaml` exist, the TOML manifest wins.
- Registry entries (`tasks/registry.json` or plugin descriptors) must match the manifest `id`, `suite`, and `version`.
- Schema-breaking changes require a new task version and an update to `SPEC_FREEZE.md`.

