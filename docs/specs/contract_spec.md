---
description: Benchmark contract specification (v0.1)
---

# Benchmark Contract Specification (v0.1)
This document defines the stable, auditable contract for TraceCore tasks, artifacts, and CLI surfaces.

## Scope
The contract covers:
- Task manifests (`task.toml`) and registry alignment
- Task interface modules (`setup.py`, `actions.py`, `validate.py`)
- Runner budgets and determinism expectations
- Run artifacts and baseline exports
- CLI behavior that reads/writes these artifacts

## Task contract
### Required files
Each task directory must contain:
- `task.toml` (preferred) or legacy `task.yaml`
- `setup.py`
- `actions.py`
- `validate.py`

### Manifest requirements (TOML)
Required fields:
- `id` (string)
- `suite` (string)
- `version` (int)
- `description` (string)
- `deterministic` (bool)
- `seed_behavior` (string: `fixed`, `stochastic`, `ignored`)
- `budgets.steps` (int)
- `budgets.tool_calls` (int)
- `action_surface.source` (string)
- `validator.entrypoint` (string)

Optional fields:
- `setup.entrypoint` (string)
- `action_surface.schema` (string, default `introspected`)

### Registry alignment
Registry entries must match the manifest `id`, `suite`, and `version`. If both `task.toml` and `task.yaml` exist, TOML wins.

## Determinism contract
- Tasks must produce identical outcomes for fixed seeds.
- Any change that alters behavior requires a new task version and updates to `SPEC_FREEZE.md`.
- Regression checks should include deterministic replays and baseline comparisons.

## Budget contract
- `budgets.steps` and `budgets.tool_calls` are enforced by the runner.
- Tasks must be solvable within declared budgets under the reference agents.

## Artifact contract
Run artifacts (`.agent_bench/runs/*.json`) are frozen evidence bundles. Every payload **must** include the following top-level fields:

- `run_id`, `trace_id`
- `agent`, `task_ref`, `task_id`, `version`
- `seed`, `success`, `failure_type`, `failure_reason`, `termination_reason`
- `steps_used`, `tool_calls_used`
- `harness_version`, `started_at`, `completed_at`
- `sandbox` (deterministic allowlists used for the run)
- `action_trace` (non-empty list)

Each entry in `action_trace` must be a dict with:

- `step`, `action_ts`
- `observation` (containing at least `step`, `task`, and `budget_remaining`)
- `action`, `result`
- `io_audit` (list; may be empty but must exist)
- `budget_after_step`, `budget_delta`

Additive fields are allowed so long as they do not remove or rename the keys above. Regression tests (`tests/test_runner_contract.py`) enforce this schema.

Baseline exports (`.agent_bench/baselines/*.json`) must include:
- `generated_at` timestamp
- `rows` containing aggregated metrics (success rate, average steps/tool calls, run counts)
- `metadata` describing the agent/task filters, limits, and generation context

The baseline export format is also guarded by regression tests (`tests/test_baseline.py`).

## Compatibility rules
- Additive fields are allowed.
- Breaking changes require a new contract version and a release note.
- The CLI must remain backward compatible with published artifacts.

## Validation tooling
Use the CLI validator to lint task packages:
```powershell
agent-bench tasks validate --path path\to\task
agent-bench tasks validate --registry
```

## Versioning
- Contract version: v0.1
- Update the version and changelog when changing required fields or behavior.
