# TraceCore + autoresearch: evidence for autonomous research

**Thesis:** Karpathy’s `autoresearch` proves how far a minimal, single-file, single-metric, fixed-time loop can go. TraceCore adds the missing evidence layer: deterministic framing, structured outcomes, replayable artifacts, and comparison tooling—without slowing the loop down.

## Why this pairing matters

`autoresearch` is intentionally tiny:
- one editable surface (`train.py`)
- a fixed 5-minute experiment budget
- a clear metric (`val_bpb`)
- rapid local iteration

What it lacks by design: durable evidence. Logs are ad hoc, diffs get lost, and comparing agents/prompts is manual. TraceCore specializes in deterministic episodes and artifact-first workflows, making every run auditable and replayable.

## What TraceCore brings

- **Deterministic episode framing** — fixed inputs, bounded loop, structured termination reasons.
- **Artifact-first evidence** — machine-readable JSON with hashes, budgets, runtime identity, and full traces.
- **Taxonomy and comparison** — normalized outcomes for filtering, dashboards, and CI/policy gates.
- **Replayability** — the ability to rerun with the same inputs to validate claims or debug regressions.

## The pragmatic starting point: a thin wrapper

We built a self-contained wrapper (see `wrapper/run_wrapper.py`) that:
- snapshots `train.py`
- runs one experiment command (e.g., `uv run train.py`)
- captures stdout/stderr and exit status
- computes the `train.py` diff
- parses `val_bpb`
- classifies the outcome (`success_improved`, `success_regressed`, `success_no_change`, `parse_failure`, `runtime_failure`, `timeout`)
- emits an artifact folder with `artifact.json`, `stdout.txt`, `stderr.txt`, and `patch.diff`
- records git commit/branch, runtime identity, system info, and baseline metric

Review recent runs with `wrapper/review_runs.py` to skim outcomes and metrics quickly.

## How this helps autonomous research

- **Evidence you can trust** — every experiment leaves behind a portable artifact instead of a console log.
- **Comparable results** — diffs + metrics + baseline context make improvements/regressions explicit.
- **Faster debugging** — outcome taxonomy separates code breakage from metric parsing issues and timeouts.
- **Agent/Prompt benchmarking** — the same task loop becomes a controlled benchmark for different agents or prompting strategies.

## What we’re not doing (yet)

- No changes to the core TraceCore runner or spec.
- No heavy orchestration or task packaging until the wrapper proves useful.
- No promise of bitwise determinism for GPU training; we aim for practical reproducibility with clear runtime identity.

## Near-term roadmap

1) **Validate on real runs** — point the wrapper at a live `autoresearch` checkout and confirm `val_bpb` parsing and outcome mapping.
2) **Tighten artifacts** — add lineage (parent/baseline IDs), richer hardware metadata, and optional git SHA requirements.
3) **Lightweight comparison tooling** — simple diff/report over emitted artifacts to surface improvements/regressions.
4) **Decide on promotion** — if the wrapper proves valuable, consider packaging this as a TraceCore task for agent benchmarking.

## How to try it

```bash
python incubation/autoresearch/wrapper/run_wrapper.py \
  --workspace-path /path/to/autoresearch \
  --command "uv run train.py" \
  --baseline-metric 1.50

python incubation/autoresearch/wrapper/review_runs.py
```

### Shim smoke test (no GPU)

Use the included torch-free shim to validate the wrapper quickly, then summarize:

```bash
python incubation/autoresearch/wrapper/run_wrapper.py \
  --workspace-path incubation/autoresearch/autoresearch \
  --command "python train.py --sleep 0.1 --val-bpb 1.11" \
  --baseline-metric 1.50

python incubation/autoresearch/wrapper/summarize_runs.py --limit 5
```

Filter to successful runs:

```bash
python incubation/autoresearch/wrapper/summarize_runs.py --include-outcomes success_improved success_no_change
```

Compare two runs (latest two by default):

```bash
python incubation/autoresearch/wrapper/compare_runs.py
python incubation/autoresearch/wrapper/compare_runs.py <run_id_A> <run_id_B>
python incubation/autoresearch/wrapper/compare_runs.py --baseline-metric 1.50
```

Sample output:

```text
found 2 artifacts in .../wrapper/runs
outcome counts -> success_improved: 1, success_regressed: 1
best metric (lower is better): 1.11 from run 20260310T183550Z-7ac4c25a in .../runs/20260310T183550Z-7ac4c25a
--- runs ---
run_id: 20260310T183550Z-7ac4c25a | outcome: success_improved | metric: 1.11 | baseline: 1.5 (delta vs baseline: -0.3900) | completed_at: 2026-03-10T18:35:51Z | dir: .../runs/20260310T183550Z-7ac4c25a
run_id: 20260310T181503Z-7b9d4998 | outcome: success_regressed | metric: 1.5117 | baseline: 1.5 (delta vs baseline: +0.0117) | completed_at: 2026-03-10T18:15:09Z | dir: .../runs/20260310T181503Z-7b9d4998
```

### Two modes

- **Torch-free shim (default here):** already swapped in under `incubation/autoresearch/autoresearch/train.py`. Runs on CPU, deterministic fake `val_bpb`, zero torch downloads. Use for laptop validation and wrapper smoke tests.
- **Full autoresearch (GPU):** restore upstream `train.py` and run `uv run train.py` on a CUDA GPU (repo cites H100). Expect ~5 min per run and large torch/CUDA downloads (~2–3 GB) the first time. 

## What success looks like

- Each experiment yields a replayable artifact with diff + metric + outcome + git context.
- Teams can compare agents/prompts on the same loop with minimal setup.
- The evidence story is clear enough to ship an adoption-focused article without touching TraceCore’s stable contracts.

## Why this matters

- **Autonomous research loop, small and fast**: autoresearch runs ~12 experiments/hour on one GPU (fixed 5-minute budget, single metric `val_bpb`, one editable file `train.py`). It proves how a tiny, agent-friendly surface can yield real ML progress.
- **TraceCore makes it auditable**: our wrapper adds sealed artifacts (diff, metric, outcome, seed, lineage, git, system info) plus validation and reporting, turning stochastic agent runs into replayable evidence—even on the CPU shim with no torch.
- **Comparability without friction**: summarize/compare/report CLIs rank runs and deltas; outcome filters separate regressions from parse/runtime failures. This works on laptops (shim) and carries over to full GPU `train.py` when needed.
