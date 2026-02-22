# Harness Runner (v0)

The harness runner executes an agent inside a task and produces a reproducible outcome.

## Responsibilities
The runner must:
- Load a task
- Initialize the environment
- Enforce the agent interface contract
- Enforce budgets
- Execute the observe → act loop
- Validate success or failure
- Emit a machine-readable result

The runner must not:
- Interpret intent
- Retry failures
- Modify agent behavior
- Judge outputs subjectively

## High-level flow
- load task
- load agent
- setup environment
- reset agent
- loop: observe → act → execute action → update budgets → check termination
- validate
- emit result

## Result format
Full schema and compatibility notes: see [`docs/trace_artifacts.md`](trace_artifacts.md).
```
{
  "task_id": "filesystem_hidden_config",
  "version": 1,
  "seed": 42,
  "success": true,
  "failure_reason": null,
  "failure_type": null,
  "steps_used": 37,
  "tool_calls_used": 12,
  "action_trace": []
}
```

## Budgets
Supported budgets:
- steps
- tool_calls
- optional wall-clock timeout

Exceeded budget = failure.

## Failure semantics

Every failed run is classified into one of these `failure_type` buckets:

- `budget_exhausted` – steps or tool calls depleted.
- `invalid_action` – schema violations or action exceptions.
- `sandbox_violation` – environment access outside the allowed surface (filesystem allowlist or guarded state).
- `logic_failure` – validator declared a terminal failure (`terminal: true`) or the run ended without other specific failure types.
- `timeout` – optional wall-clock limit tripped.
- `non_termination` – harness had to abort the run (reserved for future use).

Successful runs always emit `failure_type: null`.

### Terminal validator failures
Validators can return `{"ok": false, "terminal": true}` to halt the run immediately with a `logic_failure` termination unless they provide an explicit `termination_reason`/`failure_type` override. This is opt-in and does not affect default validator behavior.

## Determinism contract
Given the same inputs, results must be reproducible.
