# Debugging Playbook

This playbook is the fastest path from **symptom** to **evidence** to **likely fix** when a TraceCore run fails or regresses. Use it together with the run artifact in `.agent_bench/runs/`, the dashboard trace viewer, and the CLI troubleshooting guide.

## Core workflow

1. Reproduce the issue with a fixed `agent`, `task`, and `seed`.
2. Open the latest run artifact in `.agent_bench/runs/<run_id>.json`.
3. Inspect:
   - top-level outcome fields (`success`, `termination_reason`, `failure_type`, `failure_reason`)
   - `validator`
   - `action_trace`
   - `io_audit`
   - `llm_trace` when present
4. Compare against a known-good run if the issue is a regression.
5. Fix the agent/task/runtime surface that explains the earliest divergence, not just the final failure.

## Symptom -> evidence -> likely fix

### Symptom: run fails with `invalid_action`
- **Check**:
  - top-level `failure_type`
  - `action_trace[*].action`
  - any runner-provided invalid-action detail in the failing trace entry
- **Common causes**:
  - wrong action `type`
  - missing `args`
  - returning a non-dict action
  - agent emitting an action outside the task contract
- **Likely fix**:
  - align the emitted action with the task action schema and task README
  - add or update a regression test for the agent path that emitted the bad action

### Symptom: run fails with `logic_failure`
- **Check**:
  - top-level `failure_reason`
  - top-level `validator`
  - final successful/unsuccessful `set_output` behavior in `action_trace`
- **Common causes**:
  - wrong token/value format
  - validator expected a different key or output shape
  - agent found a decoy signal and submitted too early
  - task state changed but agent logic did not
- **Likely fix**:
  - inspect the validator expectation first
  - identify the exact file or signal that should have driven output
  - add test coverage for the misread case if the failure exposed an edge case

### Symptom: run fails with `budget_exhausted`
- **Check**:
  - `steps_used`, `tool_calls_used`
  - `action_trace[*].budget_after_step`
  - repeated actions or repeated paths in `action_trace`
- **Common causes**:
  - agent retry loop with no new information
  - poor stopping conditions
  - task requires more steps than the manifest realistically allows
- **Likely fix**:
  - stop the loop earlier when no new evidence is found
  - cache visited paths or failed attempts
  - only increase task budgets if the task contract genuinely requires it

### Symptom: run times out or appears stuck
- **Check**:
  - last few `action_trace` entries
  - repeated `wait` or repeated tool calls
  - wall-clock settings used for the run
- **Common causes**:
  - infinite recovery loop
  - agent waiting without a terminating condition
  - blocking or slow external integration path
- **Likely fix**:
  - add explicit termination conditions
  - bound retries and `wait` loops
  - reduce dependence on uncontrolled external behavior

### Symptom: determinism drift between two runs
- **Check**:
  - `seed`
  - `task_ref`
  - `task_hash`
  - `agent_ref`
  - `spec_version`
  - per-step differences in `action_trace`
- **Common causes**:
  - unseeded randomness
  - task code changed without versioning/freeze updates
  - timestamps or unstable ordering leaked into logic
  - external APIs or non-deterministic providers changed behavior
- **Likely fix**:
  - seed all randomness from task inputs
  - freeze task changes via versioning and `SPEC_FREEZE.md`
  - avoid wall-clock or unordered iteration in agent decisions
  - compare against baseline artifacts to locate the earliest divergence

### Symptom: telemetry looks incomplete or missing
- **Check**:
  - `action_trace[*].llm_trace`
  - environment/config flags that disable telemetry
  - whether the agent path actually emits LLM telemetry
- **Common causes**:
  - telemetry disabled by environment flag
  - agent path not using the telemetry shim/integration
  - expectation mismatch between raw artifact fields and UI rendering
- **Likely fix**:
  - verify telemetry is enabled
  - instrument the relevant agent integration path
  - confirm the artifact contains the fields before debugging dashboard rendering

### Symptom: dashboard trace and raw artifact seem inconsistent
- **Check**:
  - raw `.agent_bench/runs/<run_id>.json`
  - dashboard URL trace ID
  - whether the browser view is stale
- **Common causes**:
  - old run selected in the UI
  - browser/session cache
  - confusion between a run artifact and a sealed baseline bundle
- **Likely fix**:
  - trust the raw artifact as source of truth
  - refresh the dashboard and verify the run ID/trace ID
  - use CLI summary/list commands to confirm the latest run

## Schema quick reference for debugging

### Top-level fields you should inspect first

| Field | Why it matters |
| --- | --- |
| `success` | Fast binary outcome for the run |
| `termination_reason` | Shows whether the run ended in success, failure, timeout, or other terminal path |
| `failure_type` | Canonical failure taxonomy (`invalid_action`, `logic_failure`, `budget_exhausted`, etc.) |
| `failure_reason` | Human-readable reason normalized by the runner/validator |
| `validator` | Snapshot of validator output; often the fastest route to root cause |
| `task_ref` | Confirms exact task ID + version |
| `task_hash` | Confirms the task harness implementation used for this run |
| `agent_ref` | Confirms which agent module/path actually ran |
| `spec_version` | Tells you which artifact/runtime contract is in force |
| `budgets` | Frozen maximum step/tool-call budget for the episode |
| `wall_clock_elapsed_s` | Useful when comparing time-sensitive regressions or hangs |

### `action_trace` fields that usually explain the bug

| Field | Why it matters |
| --- | --- |
| `observation` | Shows exactly what the agent knew before acting |
| `action` | Shows what the agent decided to do |
| `result` | Shows the task/environment response |
| `io_audit` | Confirms which files/hosts were actually touched |
| `budget_after_step` | Reveals whether the run is spiraling toward exhaustion |
| `budget_delta` | Helps identify unexpectedly expensive steps |
| `llm_trace` | Captures provider/model/prompt/completion details when telemetry is enabled |

### Telemetry quick reference

When `llm_trace` is present, inspect these fields first:

| Field | Meaning |
| --- | --- |
| `request.provider` | Which provider integration was used |
| `request.model` | Which model name the agent requested |
| `request.prompt` | Rendered prompt text sent to the provider/shim |
| `request.shim_used` | Whether a deterministic shim handled the call |
| `response.completion` | Raw completion payload returned to the agent |
| `response.success` | Whether the LLM call succeeded |
| `response.error` | Error details if the LLM call failed |
| `response.tokens_used` | Token accounting when available |
| `response.timestamp` | Timing anchor for the call |

## Suggested debugging loop for regressions

```bash
python -m pytest
python -m ruff check agent_bench
tracecore runs summary --limit 5
```

Then:

1. open the failing run artifact
2. compare it with the last known-good baseline/run
3. locate the earliest step where `action`, `result`, or budget usage diverges
4. fix the decision logic or task contract responsible for that divergence
5. rerun targeted tests before rerunning the full suite

## Related docs

- [`../cli/troubleshooting.md`](../cli/troubleshooting.md)
- [`../reference/llm_telemetry.md`](../reference/llm_telemetry.md)
- [`../specs/trace_artifacts.md`](../specs/trace_artifacts.md)
- [`../contributing/external_contributor_onboarding.md`](../contributing/external_contributor_onboarding.md)
