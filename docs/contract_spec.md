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
Run artifacts (`.agent_bench/runs/*.json`) must include:
- `run_id`, `task_ref`, `seed`, `success`, `failure_type`, `failure_reason`
- `steps_used`, `tool_calls_used`
- `action_trace` (step-by-step entries)

Baseline exports (`.agent_bench/baselines/*.json`) must include:
- Aggregated metrics (success rate, average steps/tool calls)
- Metadata describing filters and generation time

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
