---
description: TraceCore core primitive (deterministic episode runtime)
---

# TraceCore Core: Deterministic Episode Runtime

TraceCore’s invariant core is a **Deterministic Episode Runtime**: a bounded runtime that executes agent-environment interaction with fixed inputs and emits replayable traces plus a structured verdict.

This is the stable nucleus that can power multiple futures (test framework, runtime platform, protocol/standard) without changing the primitive.

## Canonical definition

A Deterministic Episode Runtime executes:

`Agent + Environment + Seed + Budgets (+ Harness version + Task version)`

and produces:

`Deterministic interaction trace + Structured termination outcome + Replayable artifact`.

## What this is (and is not)

### It is
- A controlled interaction container for agent behavior under constraints.
- A deterministic execution model with reproducible outcomes.
- An artifact-first diagnostic layer for CI and regressions.

### It is not
- A leaderboard.
- An LLM-as-judge scoring framework.
- A broad intelligence benchmark.
- A hosted product requirement.

Those can be built on top. They are not the core.

## The Episode Spec (v0)

An episode is the smallest valid execution unit.

### Required inputs
1. **Agent implementation**
   - Must satisfy the reset/observe/act interface.
2. **Task/environment version**
   - Closed-world, deterministic setup and validator.
3. **Seed**
   - Explicit seed used for deterministic setup and execution.
4. **Budgets**
   - `steps`
   - `tool_calls`
   - optional wall-clock timeout
5. **Runtime identity**
   - Harness version and task version included in artifacts.

Reference contracts:
- Agent API: [`docs/agent_interface.md`](agent_interface.md)
- Task harness + determinism rules: [`docs/task_harness.md`](task_harness.md)
- Artifact schema envelope: [`docs/trace_artifacts.md`](trace_artifacts.md)

### Execution model
The runtime loop is discrete and bounded:
1. Setup environment from task + seed.
2. Reset agent with task spec.
3. Repeat observe -> act -> execute -> validate while budgets remain.
4. Terminate with structured reason.
5. Persist run artifact for replay/comparison.

## Outcome model: termination vs. failure taxonomy

TraceCore separates **exact stop condition** from **analysis bucket**.

- `termination_reason`: precise termination event from the runtime.
- `failure_type`: normalized category for filtering, dashboards, and CI policy gates.

### Canonical failure types
- `budget_exhausted`
- `invalid_action`
- `sandbox_violation`
- `logic_failure`
- `timeout`
- `non_termination`

### Mapping guidance
Typical runtime termination reasons map as follows:
- `steps_exhausted` -> `budget_exhausted`
- `tool_calls_exhausted` -> `budget_exhausted`
- `invalid_action` -> `invalid_action`
- `action_exception` -> `invalid_action`
- `sandbox_violation` -> `sandbox_violation`
- `timeout` -> `timeout`
- `logic_failure` -> `logic_failure`
- `non_termination` -> `non_termination`

Terminal validator failures (`{"ok": false, "terminal": true}`) emit `termination_reason=logic_failure` unless an explicit override is provided.

## Deterministic replay contract

Replay is a first-class property, not a convenience feature.

Given the same:
- task id/version,
- agent implementation,
- seed,
- budgets,
- and compatible harness/task contracts,

the runtime must produce reproducible outcomes with a stable trace envelope, or a diff that is explicit and inspectable.

### Why this matters
If an episode cannot be replayed deterministically, it is not a reliable infrastructure primitive; it is only a demo.

## Artifact contract (core surface)

Every episode must emit a machine-readable artifact suitable for automation and audit. Core fields include:
- identity (`run_id`, `trace_id`, `task_ref`, `agent`, `harness_version`)
- control inputs (`seed`)
- outcome (`success`, `termination_reason`, `failure_type`, `failure_reason`)
- bounded usage (`steps_used`, `tool_calls_used`)
- full `action_trace`

Additive schema evolution is acceptable; breaking schema changes require versioning and release notes.

## Why this is the right strategic focus now

Defining this primitive cleanly avoids early identity lock-in and preserves optionality:
- Want pytest-for-agents? Wrap episodes in test runners.
- Want runtime packaging? Package environments around episode contracts.
- Want a standard/protocol? Publish this spec as the interoperable core.

All three paths depend on the same deterministic episode runtime.

## Practical operator value

This core gives teams:
1. **Regression detection** with stable seeds and baseline compare workflows.
2. **Actionable failures** via structured taxonomy and full trace context.
3. **CI-native gating** using deterministic pass/fail and policy thresholds.
4. **Auditable evidence** through persisted run artifacts and replayability.

## One-line mental model

If pytest tests functions, **TraceCore executes deterministic episodes**.

If Docker packages containers, **TraceCore packages bounded agent-environment interactions**.
