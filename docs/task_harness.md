# Task Harness Specification (v0)

This document defines what a task is, how it runs, and what agents are allowed to touch.

## 1. What is a task?
A task is a closed-world environment with:
- a deterministic initial state
- a constrained action surface
- a single success condition

A task does not test intelligence. It tests whether an agent can operate correctly under constraints.

## 2. Task directory layout
Each task is a self-contained directory:
```
tasks/
  <task_id>/
    task.toml   (preferred; task.yaml legacy)
    setup.py
    actions.py
    validate.py
    README.md   (optional)
```
Nothing outside this directory may influence task behavior.

## 3. task.toml — Task metadata (frozen)
This file is purely declarative. Legacy `task.yaml` files are still accepted but should be considered read-only.
```toml
id = "filesystem_hidden_config"
suite = "filesystem"
version = 1
description = "Extract the correct configuration value from the filesystem."
deterministic = true
seed_behavior = "fixed"

[budgets]
steps = 200
tool_calls = 50

[action_surface]
source = "actions.py"
schema = "introspected"

[validator]
entrypoint = "validate.py:validate"
```
Rules:
- No logic
- No conditionals
- No imports
- Once released, this file is immutable
- Changing behavior requires a new version

## 4. setup.py — Environment initialization
Creates the world.
Responsibilities:
- Create files, directories, logs, mock services
- Seed all randomness
- Initialize hidden state
Rules:
- Runs before the agent starts
- Agent cannot read or inspect setup code
- Must be deterministic given the seed
- No network access
- No wall-clock dependence

## 5. actions.py — The action surface
Defines everything the agent can do.
If an action is not here, it does not exist.
Rules:
- All actions are synchronous, logged, and budgeted
- No shell access
- No filesystem escape
- No reflection or inspection

Error handling:
- Actions return either a successful result or a structured error
- Never exceptions

## 6. Step model
The harness runs in discrete steps.
Each step:
- Agent receives an observation
- Agent emits exactly one action
- Harness executes the action
- Result is recorded
- Budgets are decremented

No action batching. No background execution.

## 7. Budgets & termination
Every task enforces budgets.
Budgets:
- steps
- tool_calls
- optional wall-clock timeout

A task ends when:
- validate() returns success
- Agent emits an invalid action
- Any budget is exhausted
- Harness encounters a fatal error

## 8. Observability model
Agents can observe only what the task allows.
Agents can see:
- Task description
- Action results
- Their own past actions
- Explicit visible state (if provided)

Agents cannot see:
- Setup code
- Validation logic
- Hidden files or state
- Ground truth answers

## 9. validate.py — Success criteria
Defines success.
Rules:
- Deterministic
- Final-state only
- No LLMs
- No partial credit
- No time-based logic

## 10. Determinism contract
Given task id + version, random seed, and agent implementation, outcomes must be reproducible.

## 11. Anti-cheating guarantees
The harness enforces:
- Process isolation
- Read-only task metadata
- No filesystem escape
- No environment introspection
- No dynamic imports outside the task

## 12. What makes a good task?
A good task:
- Fails brittle agents quickly
- Rewards conservative behavior
- Has exactly one right outcome
- Surfaces why the agent failed

A bad task:
- Requires guessing
- Encourages hacks
- Depends on timing
- Takes minutes to run

## 13. Explicit non-goals
The task harness does not:
- Simulate the real world
- Test creativity
- Judge explanations
- Optimize for realism

## 14. Diagnostics contract
- Every run produces a JSON artifact under `.agent_bench/runs/` that captures metadata (run_id, trace_id, timestamps, harness version), per-step traces, and outcome metrics.
- Trace viewers (CLI + Web UI) must surface that artifact verbatim; no summarization that hides the raw steps.
- Baseline tables derive only from persisted artifacts to keep comparisons reproducible.
- When freezing a task version, capture the relevant run IDs and carry them forward as regression fixtures.
