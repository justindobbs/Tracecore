# Performance Baselines

Use this guide when generating, reviewing, and publishing Phase 6 performance artifacts from `scripts/perf_harness.py`.

The current harness is intentionally a maintainer-facing scaffold: it reuses the existing batch runner and metrics pipeline, emits JSON artifacts into `deliverables/perf/`, and provides enough structure to establish initial thresholds before the full ≥1k benchmark program is finalized.

## When to use this document

Use this workflow when one or more of the following is true:

- you are validating that a runtime or agent change did not materially regress batch throughput or artifact growth
- you need a repeatable maintainer command for generating `deliverables/perf/` evidence
- you want an initial set of CI or release thresholds before rendered dashboards exist
- you are preparing to scale the harness from the default slice to the PRD target of `--episodes 1000`

## Recommended commands

### Default maintainer slice

Use the small repeatable slice for everyday validation and pull-request level checks:

```powershell
python scripts/perf_harness.py --episodes 24 --workers 4 --strict-spec
```

### Larger manual benchmark slice

Use an explicit larger run when collecting stronger evidence for the Phase 6 scalability item:

```powershell
python scripts/perf_harness.py --episodes 1000 --workers 8 --strict-spec
```

Run larger slices on a relatively quiet machine and record the host context in the resulting change description or release notes.

### Optional compressed bundle

If you want a single lossless archive of the generated artifacts without changing the default JSON outputs, add `--compress`:

```powershell
python scripts/perf_harness.py --episodes 24 --workers 4 --strict-spec --compress
```

This emits `perf-artifacts-<stamp>.zip` alongside the individual JSON files.

## Artifact set

The harness currently writes four JSON artifacts into `deliverables/perf/`, plus an optional zip bundle when `--compress` is enabled.

### 1. `perf-manifest-<stamp>.json`

Use the manifest as the run descriptor. It records:

- generation timestamp
- episode count
- worker count
- timeout
- strict-spec mode
- scenario definition
- available system sampling fields
- emitted artifact set

### 2. `perf-summary-<stamp>.json`

Use the summary for quick release or CI review. It currently captures:

- total episodes
- success / failure counts
- max wall-clock time
- failure reasons
- run-artifact disk footprint from `.agent_bench/runs`
- aggregate artifact-size and LLM telemetry-verbosity totals derived from run results
- optional `psutil`-based CPU and memory samples

### 3. `perf-metrics-<stamp>.json`

Use the metrics artifact for task- or agent-level rollups. This comes from the existing run metrics pipeline and stays aligned with the rest of TraceCore’s reporting surfaces.

### 4. `perf-series-<stamp>.json`

Use the series artifact for charting and regression review. Each row is a single episode and includes:

- episode number
- episode index
- agent
- task reference
- seed
- success flag
- wall-clock time
- error string, if any
- serialized artifact size in bytes
- LLM telemetry entry count
- prompt/completion byte volume
- token usage total when present

This file is the preferred source for simple latency charts and distribution analysis.

### Optional 5. `perf-artifacts-<stamp>.zip`

When `--compress` is enabled, the harness also emits a lossless zip bundle containing the manifest, summary, metrics, and series files for easier archival or CI upload.

## Initial threshold guidance

These thresholds are intentionally conservative until the full ≥1k benchmark evidence set is published.

### Default 24-episode maintainer slice

Treat the following as the initial review thresholds:

- `failure_count == 0`
- `max_wall_clock_s <= 15`
- `run_artifacts.total_bytes <= 2_000_000`
- `run_artifacts.avg_bytes <= 150_000`
- no unexpected new `failure_reasons`

### Larger manual benchmark slice

For larger runs, focus on trend stability rather than a single hard cutoff:

- success rate should remain effectively stable relative to the default slice
- `perf-series` should not show obvious long-tail latency spikes caused by runtime regressions
- artifact growth should remain roughly linear with episode count
- optional CPU / memory samples should not indicate runaway growth between repeated runs on the same host

If you need CI gating today, prefer the default slice and compare new artifacts against a checked-in or archived reference from the same machine class.

## Review workflow

### 1. Generate artifacts

Run the harness with the intended episode count and workers.

### 2. Inspect the summary first

Start with `perf-summary-*.json` to confirm:

- zero unexpected failures
- acceptable max latency
- reasonable artifact footprint

### 3. Inspect the series artifact

Use `perf-series-*.json` to answer:

- did one scenario spike disproportionately?
- are failures clustered on a single task or seed pattern?
- is latency increasing late in the run?

### 4. Inspect aggregate metrics

Use `perf-metrics-*.json` to confirm the broader run-level rollup still matches expectations for success rate, failure taxonomy, and wall-clock summaries.

## Suggested release / CI posture

For now, use the performance harness as a maintainer and release signal rather than a hard release blocker for every environment.

Recommended policy:

- pull requests with runtime-affecting perf work: run the default 24-episode slice locally or in a focused CI job
- release preparation: run at least one larger benchmark slice and archive the emitted artifacts
- when host stability matters, compare results only against baselines from the same machine class or CI runner image

## Known limitations

The current scaffold does **not** yet provide all final Phase 6 deliverables.

Still open:

- published ≥1k benchmark evidence committed as a baseline program
- rendered chart outputs checked into `deliverables/perf/`
- threshold enforcement wired directly into CI alerts
- richer time-series sampling beyond the current per-episode rows

## Related docs

- [Release process](release_process.md)
- [Manual verification checklist](manual_verification.md)
- [Artifact migration playbook](artifact_migration_playbook.md)
