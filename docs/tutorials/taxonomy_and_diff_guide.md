# Taxonomy Metadata & Diff Routing Guide

This tutorial explains how to extend TraceCore's failure taxonomy, use `tracecore diff` to route structured diffs into dashboards and monitoring pipelines, and write regression tests that cover new taxonomy fields.

---

## 1. Understanding the taxonomy fields

Every run artifact carries two taxonomy fields in addition to the standard outcome fields:

| Field | Type | Description |
|-------|------|-------------|
| `failure_type` | `str \| null` | High-level failure class (e.g. `budget_exceeded`, `logic_failure`, `tool_call_error`). `null` on success. |
| `termination_reason` | `str` | Why the episode ended (e.g. `success`, `budget_exceeded`, `validator_rejected`). Always present. |

Both fields appear at the top level of every `.agent_bench/runs/*.json` artifact.

---

## 2. Extending taxonomy metadata in a custom task

Add `failure_type` and `termination_reason` to your validator's return value so the runner can propagate them:

```python
# tasks/my_task/validate.py

def validate(env) -> dict:
    output = env.fs.read("/tmp/my_task/output.txt") if env.fs.exists("/tmp/my_task/output.txt") else ""

    if "SECRET_VALUE" in output:
        return {
            "success": True,
            "termination_reason": "success",
        }

    if not env.fs.exists("/tmp/my_task/output.txt"):
        return {
            "success": False,
            "failure_type": "logic_failure",
            "termination_reason": "validator_rejected",
            "failure_reason": "Agent did not write output.txt",
        }

    return {
        "success": False,
        "failure_type": "logic_failure",
        "termination_reason": "validator_rejected",
        "failure_reason": "output.txt present but secret not recovered",
    }
```

**Available `failure_type` values** (from `agent_bench/runner/failures.py`):

- `budget_exceeded` — agent ran out of steps or tool calls
- `logic_failure` — validator rejected the outcome
- `tool_call_error` — action raised an unhandled exception
- `timeout` — wall-clock budget exceeded
- `spec_violation` — strict-spec check failed

---

## 3. Diffing runs with taxonomy

### CLI

```bash
# Default: pretty-printed with taxonomy + budget delta always shown
tracecore diff <run_id_a> <run_id_b>

# Machine-readable JSON with all fields
tracecore diff <run_id_a> <run_id_b> --format json

# OTLP-compatible spans for each run with taxonomy embedded
tracecore diff <run_id_a> <run_id_b> --format otlp
```

The diff output always includes:

```json
{
  "taxonomy": {
    "same_failure_type": false,
    "same_termination_reason": false,
    "run_a": { "failure_type": null, "termination_reason": "success" },
    "run_b": { "failure_type": "budget_exceeded", "termination_reason": "budget_exceeded" }
  },
  "budget_delta": {
    "steps": 8,
    "tool_calls": 12,
    "wall_clock_s": 3.5
  }
}
```

### API

```bash
# Same diff output available at the /api/runs/diff endpoint
curl "http://localhost:8000/api/runs/diff?a=<run_id_a>&b=<run_id_b>"
```

### Dashboard

Open the **Compare** tab on the TraceCore dashboard, enter two run IDs, and click **Diff Runs**. The panel now shows:

- **Taxonomy shift** — failure type and termination reason for each run with a match/changed indicator
- **Budget delta (B − A)** — step count, tool call, and wall-clock deltas with colour coding
- **Delta view** — per-step action diff table
- **IO Drift** — added/removed io_audit entries per step

---

## 4. Routing diffs into monitoring pipelines

### OTLP export

Export a run as OTLP spans for Grafana Tempo, Jaeger, or Honeycomb:

```bash
tracecore export otlp <run_id> > run_spans.json
tracecore export otlp <run_id> --output run_spans.json
```

To export both runs from a diff as OTLP in one command:

```bash
tracecore diff <run_id_a> <run_id_b> --format otlp > diff_spans.json
```

The OTLP payload includes `tracecore.failure_type` and `tracecore.termination_reason` as span attributes on the root episode span, making them queryable in any OTLP backend.

### Piping into CI checks

```bash
# Fail CI if taxonomy shifts between baseline and current run
DIFF=$(tracecore diff "$BASELINE_RUN_ID" "$CURRENT_RUN_ID" --format json)
SAME=$(echo "$DIFF" | python -c "import sys,json; d=json.load(sys.stdin); print(d['taxonomy']['same_failure_type'] and d['taxonomy']['same_termination_reason'])")
if [ "$SAME" != "True" ]; then
  echo "Taxonomy shifted — review diff output"
  exit 1
fi
```

---

## 5. Writing regression tests for taxonomy fields

```python
from agent_bench.runner.runner import run
from agent_bench.runner.baseline import diff_runs, load_run_artifact

def test_task_failure_type_on_budget_exceeded():
    result = run("agents/toy_agent.py", "my_task@1", seed=0)
    assert result.get("failure_type") in (None, "budget_exceeded", "logic_failure")
    assert result.get("termination_reason") is not None

def test_diff_detects_taxonomy_shift():
    run_a = load_run_artifact("path/to/baseline.json")
    run_b = load_run_artifact("path/to/current.json")
    diff = diff_runs(run_a, run_b)
    # Assert the diff includes taxonomy block
    assert "taxonomy" in diff
    assert "same_failure_type" in diff["taxonomy"]
    assert "budget_delta" in diff
```

---

## 6. Metrics dashboard

`tracecore runs metrics --format table` now shows both:
- **Failure Type** column — counts by `failure_type` per task+agent
- **Termination Reason** column — counts by `termination_reason` per task+agent

These are also available in the `/metrics` dashboard in the browser.
