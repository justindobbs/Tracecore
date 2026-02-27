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
- `sandbox` (object)
- `validator` (object | null)
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
  "io_audit": [
    { "type": "fs", "op": "list_dir", "path": "/app" }
  ],
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
- `io_audit` (array) — per-step filesystem/network access entries (`type: fs|net`, plus `path` or `host`).
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
Subset of the top-level run artifact fields, plus `trace_entry_count` and `sandbox`:
`run_id`, `trace_id`, `agent`, `task_ref`, `task_id`, `version`, `seed`, `harness_version`, `started_at`, `completed_at`, `success`, `termination_reason`, `failure_type`, `failure_reason`, `steps_used`, `tool_calls_used`, `trace_entry_count`, `sandbox`.

### `tool_calls.jsonl`
One JSON object per line, one line per trace entry:
```json
{"step": 1, "action_ts": "...", "action": {...}, "result": {...}, "io_audit": [...], "budget_after_step": {...}, "budget_delta": {...}}
```
`io_audit` is required (may be an empty list).

### `validator.json`
```json
{
  "success": true,
  "termination_reason": "success",
  "failure_type": null,
  "failure_reason": null,
  "metrics": { "steps_used": 4, "tool_calls_used": 4 },
  "validator": { "ok": true }
}
```

The runner now stores a normalized snapshot of the task validator response in both the run artifact (`validator` top-level key) and the bundle snapshot. For terminal failures this includes `failure_reason`, `failure_type`, and `termination_reason` fields after taxonomy normalization.

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

## Analysis UX: Comparing Runs

The `agent-bench baseline --compare` command provides rich diff output for analyzing trace divergence and budget drift between two runs.

### Integrity verification workflow

Baseline bundles should be hashed and verified automatically so CI and auditors can trust the artifacts:

```sh
# 1. Write + verify the latest run as a bundle (includes integrity report in JSON payload)
agent-bench baseline --agent agents/toy_agent.py --task filesystem_hidden_config@1 --bundle

# 2. Verify an existing bundle directory explicitly (returns non-zero if any hash mismatches)
agent-bench baseline --verify .agent_bench/baselines/<run_id>

# 3. Use standalone helper when scripting
agent-bench bundle verify .agent_bench/baselines/<run_id>
```

The `--bundle` path prints `{ "bundle_dir": ..., "verify": {"ok": bool, "errors": [...] } }` so CI can fail fast when integrity fails, satisfying the Phase 1 requirement that hashing is enforced by default.

### CLI diff formats

**Pretty format (default)**
```sh
agent-bench baseline --compare .agent_bench/baselines/<run_id_a> <run_id_b>
```

Displays:
1. **Status panel**: `✓ IDENTICAL`, `△ DIFFERENT`, or `✗ INCOMPATIBLE`
2. **Run Summary table**: agent, task, success, seed (with match indicators)
3. **Budget Usage table**: steps and tool calls with delta highlighting
   - Red delta: current run used more budget than baseline
   - Green delta: current run used less budget
4. **Per-Step Differences table** (first 5 divergences): shows action type changes

**With taxonomy** (add `--show-taxonomy`):
```sh
agent-bench baseline --compare <run_a> <run_b> --show-taxonomy
```

Adds a **Failure Taxonomy table** showing `failure_type` and `termination_reason` for both runs, making it easy to spot when a run changed from `logic_failure` to `budget_exhausted`, etc.

**Text format** (legacy):
```sh
agent-bench baseline --compare <run_a> <run_b> --format text
```

Prints a simple key-value summary without rich formatting.

**JSON format** (for tooling):
```sh
agent-bench baseline --compare <run_a> <run_b> --format json
```

Emits the full diff structure with `summary`, `run_a`, `run_b`, and `step_diffs` arrays for programmatic analysis.

### Interpreting budget drift

- **Positive delta** (red): current run consumed more steps/tool_calls than baseline
  - May indicate agent inefficiency, new exploration paths, or task changes
  - Check per-step diffs to see where extra calls occurred
- **Negative delta** (green): current run was more efficient
  - Verify success still matches; efficiency gains are only valid if the task still passes
- **Zero delta with divergence**: agent took same number of steps but different actions
  - Often indicates non-determinism or logic changes; review trace carefully

### Interpreting failure taxonomy

When `--show-taxonomy` is enabled:
- **Same failure type**: agent behavior is consistent (good for regression testing)
- **Different failure type**: indicates a behavioral change
  - `logic_failure` → `budget_exhausted`: agent is now less efficient or stuck in a loop
  - `budget_exhausted` → `logic_failure`: agent fails faster (may indicate a bug fix or new validation)
  - Any change to/from `sandbox_violation` or `invalid_action`: critical contract violation

### Example workflow

```sh
# Record baseline
agent-bench run --agent agents/my_agent.py --task my_task@1 --seed 0 --record

# Later, after code changes, run again
agent-bench run --agent agents/my_agent.py --task my_task@1 --seed 0

# Compare with pretty output + taxonomy
agent-bench baseline --compare \
  .agent_bench/baselines/<baseline_run_id> \
  <new_run_id> \
  --show-taxonomy
```

---

## Web UI Analysis UX

The TraceCore web UI provides visual analysis tools for trace inspection and run comparison alongside the CLI diff tools.

### Trace Viewer Enhancements

**Budget burn chart**
- Canvas-based line chart showing remaining steps (cyan) and tool calls (blue) over the episode
- Helps identify budget exhaustion patterns and efficiency trends
- Legend clarifies which line represents which metric

**Outcome taxonomy badge**
- Color-coded badge showing run outcome:
  - Green: Success
  - Yellow: budget_exhausted
  - Red: invalid_action, sandbox_violation, logic_failure
- Provides immediate visual feedback on failure type

### Baseline Comparison Enhancements

**Delta view table**
- Per-step comparison showing baseline vs current actions
- Highlights result changes between runs
- First 10 divergences displayed for quick triage

**Color-coded budget drift**
- Numeric deltas with color indicators:
  - Red (positive): Current run used more budget than baseline
  - Green (negative): Current run was more efficient
  - Gray (zero): No change in budget usage

**Recent runs taxonomy badges**
- Inline badges in the runs list for quick outcome scanning
- Consistent color scheme with trace viewer badges

### Usage Workflow

1. **Trace inspection**: Click any run's "trace" link to view budget burn chart and outcome badge
2. **Compare runs**: Use Baselines → Compare section to see delta view and budget drift
3. **Pattern detection**: Look for budget plateaus (stuck in loops) or sharp drops (inefficient actions)

### Technical Notes

- Budget series extracted from `observation.budget_remaining` in each trace entry
- Taxonomy badges derived from `failure_type` field with fallback to termination_reason
- Delta calculations use the same normalization as CLI diff (steps/tool_calls only)
- Chart rendering uses 2D canvas with device pixel ratio scaling for crisp display

---

## Structured Trace Export (OTLP)

TraceCore can convert any run artifact into an **OpenTelemetry Protocol (OTLP) JSON** payload for ingestion into Grafana Tempo, Jaeger, Honeycomb, or any other OTLP-compatible backend.

### Mapping

| TraceCore concept | OTLP concept |
|---|---|
| Run | `ResourceSpans` (one per run) |
| Episode (root) | Root `Span` — name `episode/<task_ref>` |
| Trace entry (step) | Child `Span` — name `step/<n>/<action_type>` |
| `failure_type`, `termination_reason` | Span attributes (`tracecore.*`) |
| `io_audit` entries | Span attributes `tracecore.io_audit.fs_paths` / `net_hosts` |

Every span carries the full taxonomy (`tracecore.success`, `tracecore.failure_type`, `tracecore.termination_reason`, `tracecore.steps_used`, etc.) so failure patterns are queryable without manual schema mapping.

### CLI usage

```sh
# Print OTLP JSON to stdout
agent-bench export otlp <run_id_or_path>

# Write to file
agent-bench export otlp <run_id_or_path> --output trace.otlp.json
```

### Python API

```python
from agent_bench.runner.export_otlp import run_to_otlp, export_otlp_json

payload = run_to_otlp(result)          # dict — ready for json.dumps
json_str = export_otlp_json(result)    # convenience string wrapper
json_str = export_otlp_json(result, indent=2)
```

### Resource attributes

The `resource` block of every export includes:

| Attribute | Value |
|---|---|
| `service.name` | `"tracecore"` |
| `service.version` | harness version string |
| `tracecore.task_ref` | e.g. `"filesystem_hidden_config@1"` |

### Span timing notes

- Root span: `started_at` → `completed_at` from the run artifact (real wall-clock duration).
- Step spans: `action_ts` timestamp with a 1 ms synthetic duration (TraceCore does not measure per-step latency by default).

---

## Episode Config Schema

An *episode config* is a JSON file that pins agent, task, seed, model, provider, and per-episode budget overrides without modifying task manifests. It enables reproducible model-comparison experiments and CI parameterisation.

### Schema

```json
{
  "agent": "agents/my_agent.py",
  "task_ref": "filesystem_hidden_config@1",
  "seed": 42,
  "model": "gpt-4o",
  "provider": "openai",
  "budget_override": { "steps": 50, "tool_calls": 20 },
  "wall_clock_timeout_s": 120,
  "metadata": { "experiment": "gpt4o-vs-mini", "ci_run": "456" },
  "schema_version": "1"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `agent` | string | ✓ | Path to agent file passed to the runner |
| `task_ref` | string | ✓ | Task reference in `<id>@<version>` format |
| `seed` | int | — | Deterministic seed (default: `0`) |
| `model` | string\|null | — | Model name hint forwarded to the agent via `task_spec` |
| `provider` | string\|null | — | Provider hint (`"openai"`, `"anthropic"`, etc.) |
| `budget_override` | object | — | Per-run overrides for `steps` and/or `tool_calls`; must be positive integers |
| `wall_clock_timeout_s` | int\|null | — | Wall-clock timeout forwarded to `--timeout` |
| `metadata` | object | — | Arbitrary tags merged into run artifact top-level fields |
| `schema_version` | string | — | Internal schema version; do not set manually |

### CLI usage

```sh
# Run from an episode config (CLI flags override config values)
agent-bench run --from-config episode.json

# Override seed on top of config
agent-bench run --from-config episode.json --seed 99
```

### Python API

```python
from agent_bench.runner.episode_config import EpisodeConfig, load_episode_config

# Create and write
cfg = EpisodeConfig(
    agent="agents/my_agent.py",
    task_ref="filesystem_hidden_config@1",
    seed=42,
    budget_override={"steps": 50},
    metadata={"experiment": "ablation-1"},
)
cfg.write("episode.json")

# Load from file
cfg2 = EpisodeConfig.from_file("episode.json")

# Merge with task default budget
effective = cfg2.effective_budget({"steps": 200, "tool_calls": 40})
# → {"steps": 50, "tool_calls": 40}
```

### Budget merging rules

`effective_budget(task_default)` merges `budget_override` into the task's `default_budget`:
- Override keys replace task defaults; unmentioned keys are kept from the task manifest.
- Zero or negative override values are **ignored** (task default wins) to prevent accidental zero-budget configs.

---

## Compatibility notes
- Additive fields are allowed. Removals or renames require a version bump and changelog entry.
- Consumers should ignore unknown keys to remain forward compatible.
- `metrics` is reserved for derived values (steps/tool_calls are mirrored here for tooling).
- Action/result payloads are task-defined; only the surrounding envelope is standardized.
- `action_ts` and `budget_delta` were added in v0.7.0 (additive; old consumers unaffected).
- `io_audit` and `manifest.sandbox` were added in v0.9.0 (additive; old consumers should ignore unknown keys).

