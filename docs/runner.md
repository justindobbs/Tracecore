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
```
{
  "task_id": "filesystem_hidden_config",
  "version": 1,
  "seed": 42,
  "success": true,
  "failure_reason": null,
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
Invalid action, timeout, budget exceeded, or exception in agent = failure.

## Determinism contract
Given the same inputs, results must be reproducible.
