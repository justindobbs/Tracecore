---
description: Run artifact + trace schema
---

# Run Artifact Schema (v0)

Every run produces a JSON artifact in `.agent_bench/runs/`. This schema is stable and meant for tooling, diffs, and CI regression checks.

## Top-level fields
- `task_id` (string)
- `version` (int)
- `seed` (int)
- `success` (bool)
- `termination_reason` (string)
- `failure_reason` (string | null)
- `failure_type` (string | null)
- `steps_used` (int)
- `tool_calls_used` (int)
- `metrics` (object)
- `action_trace` (array)
- `run_id` (string, UUID hex)
- `trace_id` (string, UUID hex)
- `agent` (string, path)
- `task_ref` (string, `<id>@<version>`)
- `started_at` (string, ISO 8601)
- `completed_at` (string, ISO 8601)
- `harness_version` (string)

## Trace entry schema
Each entry in `action_trace` captures one observe-act step:
```json
{
  "step": 1,
  "action_ts": "2026-02-20T19:00:00.000000+00:00",
  "observation": {
    "step": 1,
    "task": { "id": "filesystem_hidden_config", "description": "..." },
    "last_action": null,
    "last_action_result": null,
    "visible_state": {},
    "budget_remaining": { "steps": 199, "tool_calls": 39 }
  },
  "action": { "type": "list_dir", "args": { "path": "." } },
  "result": { "ok": true, "files": ["config", "readme.txt"] },
  "budget_after_step": { "steps": 198, "tool_calls": 38 },
  "budget_delta": { "steps": 1, "tool_calls": 1 }
}
```

### Trace entry fields
- `step` (int) — 1-indexed step counter within the episode.
- `action_ts` (string, ISO 8601) — UTC timestamp at which the action was dispatched.
- `observation` (object) — full observation dict passed to the agent before this step.
- `action` (object) — the action dict returned by the agent (`type` + `args`).
- `result` (object) — the action's return value from the task actions module.
- `budget_after_step` (object) — remaining `steps` and `tool_calls` after this step.
- `budget_delta` (object) — budget units consumed this step (`steps: 1, tool_calls: 1` for normal actions).

---

## Baseline bundle format

A *baseline bundle* is a directory produced by `agent_bench.runner.bundle.write_bundle()` that captures a certified run for replay verification and ledger submission.

### Bundle layout
```
.agent_bench/baselines/<run_id>/
    manifest.json        # run metadata + ledger-linkable fields
    tool_calls.jsonl     # one JSON line per trace entry (action + result + timestamps)
    validator.json       # final validation snapshot (success, failure_type, metrics)
    integrity.sha256     # SHA-256 hashes of the three files above
```

### `manifest.json` fields
Subset of the top-level run artifact fields, plus `trace_entry_count`:
`run_id`, `trace_id`, `agent`, `task_ref`, `task_id`, `version`, `seed`, `harness_version`, `started_at`, `completed_at`, `success`, `termination_reason`, `failure_type`, `failure_reason`, `steps_used`, `tool_calls_used`, `trace_entry_count`.

### `tool_calls.jsonl`
One JSON object per line, one line per trace entry:
```json
{"step": 1, "action_ts": "...", "action": {...}, "result": {...}, "budget_after_step": {...}, "budget_delta": {...}}
```

### `validator.json`
```json
{
  "success": true,
  "termination_reason": "success",
  "failure_type": null,
  "failure_reason": null,
  "metrics": { "steps_used": 4, "tool_calls_used": 4 }
}
```

### `integrity.sha256`
SHA-256 digest of each bundle file, one per line in `<digest>  <filename>` format (compatible with `sha256sum -c`).

### Python API
```python
from agent_bench.runner.bundle import write_bundle, verify_bundle
from pathlib import Path

bundle_dir = write_bundle(result)                    # writes to .agent_bench/baselines/<run_id>/
bundle_dir = write_bundle(result, dest=Path("out"))  # custom destination

report = verify_bundle(bundle_dir)
assert report["ok"], report["errors"]
```

---

## Compatibility notes
- Additive fields are allowed. Removals or renames require a version bump and changelog entry.
- Consumers should ignore unknown keys to remain forward compatible.
- `metrics` is reserved for derived values (steps/tool_calls are mirrored here for tooling).
- Action/result payloads are task-defined; only the surrounding envelope is standardized.
- `action_ts` and `budget_delta` were added in v0.7.0 (additive; old consumers unaffected).

