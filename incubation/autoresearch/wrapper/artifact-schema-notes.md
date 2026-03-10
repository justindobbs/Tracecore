# Artifact schema notes

This document describes the initial JSON shape for a thin `autoresearch` wrapper artifact. It is intentionally local to incubation and not a normative TraceCore schema.

## Proposed example

```json
{
  "run_id": "20260309T183000Z-001",
  "started_at": "2026-03-09T18:30:00Z",
  "completed_at": "2026-03-09T18:35:12Z",
  "workspace_path": "/path/to/autoresearch",
  "baseline_file": "train.py",
  "command": "uv run train.py",
  "exit_code": 0,
  "stdout_path": "runs/20260309T183000Z-001/stdout.txt",
  "stderr_path": "runs/20260309T183000Z-001/stderr.txt",
  "patch_diff": "diff --git a/train.py b/train.py ...",
  "metric": {
    "name": "val_bpb",
    "value": 1.4821,
    "parsed_from": "stdout"
  },
  "baseline": {
    "metric_name": "val_bpb",
    "metric_value": 1.5
  },
  "outcome": "success_improved",
  "failure_reason": null,
  "runtime_identity": {
    "name": "tracecore-autoresearch-wrapper",
    "version": "0.1.0"
  },
  "git": {
    "commit": "abc123",
    "branch": "main"
  },
  "system_info": {
    "platform": "linux",
    "python": "3.10"
  },
  "notes": null
}
```

## Field intent

- `run_id`
  - local unique identifier for one wrapped experiment
- `started_at`, `completed_at`
  - enable duration analysis and simple ordering
- `workspace_path`
  - records which checkout was used
- `baseline_file`
  - keeps the editable surface explicit
- `command`
  - exact invocation for replay attempts
- `exit_code`
  - separates process failure from metric failure
- `stdout_path`, `stderr_path`
  - preserves raw evidence outside the JSON body
- `patch_diff`
  - captures what changed in `train.py`
- `metric`
  - stores parsed optimization output in a task-local shape
- `baseline`
  - records the comparison target used for improved/regressed/no-change classification
- `outcome`
  - simplified local classification for the prototype
- `failure_reason`
  - freeform explanation when outcome is not successful
- `runtime_identity`
  - makes the wrapper versioned from day one
- `git`
  - records the workspace commit and branch when available
- `system_info`
  - useful for comparing results across environments

## Open questions

- Should patch content live inline or only as `patch.diff` on disk?
- Should parent/baseline lineage be part of the first artifact version?
- At what point should this shape converge toward existing TraceCore run artifacts?
