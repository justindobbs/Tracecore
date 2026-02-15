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
  "budget_after_step": { "steps": 199, "tool_calls": 39 }
}
```

## Compatibility notes
- Additive fields are allowed. Removals or renames require a version bump and changelog entry.
- Consumers should ignore unknown keys to remain forward compatible.
- `metrics` is reserved for derived values (steps/tool_calls are mirrored here for tooling).
- Action/result payloads are task-defined; only the surrounding envelope is standardized.

