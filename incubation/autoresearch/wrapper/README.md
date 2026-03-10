# Thin wrapper prototype

This directory defines the first practical integration target between TraceCore and `autoresearch`: a thin wrapper that captures evidence around an `autoresearch` experiment run without requiring changes to TraceCore's core runtime or specification.

## Goal

Wrap a single `autoresearch` experiment loop with structured capture of:
- the code change being evaluated
- the command that was executed
- the resulting metric output
- runtime and environment identity
- a normalized outcome classification

The wrapper is intentionally smaller than a full TraceCore task package.

## Current prototype

The first standalone prototype lives in `run_wrapper.py`.

A minimal inspection utility lives in `review_runs.py`.

Example usage:

```bash
python incubation/autoresearch/wrapper/run_wrapper.py \
  --workspace-path /path/to/autoresearch \
  --command "uv run train.py" \
  --baseline-metric 1.50
```

The script emits one run folder under `wrapper/runs/<run_id>/` containing:
- `artifact.json`
- `stdout.txt`
- `stderr.txt`
- `patch.diff`

Recent artifacts can be reviewed with:

```bash
python incubation/autoresearch/wrapper/review_runs.py
```

## What the first prototype should do

Given an `autoresearch` workspace, the wrapper should:
1. snapshot the baseline state of `train.py`
2. run one candidate experiment command
3. capture stdout/stderr and exit status
4. compute the diff applied to `train.py`
5. parse the resulting metric payload, especially `val_bpb`
6. emit a JSON artifact into a local output directory

## Non-goals

The first prototype should not:
- modify TraceCore runner internals
- claim full spec compliance
- depend on new stable CLI commands
- introduce task packaging or validator contracts yet
- solve perfect determinism for GPU training

## Minimal inputs

The wrapper should accept at least:
- `workspace_path`
- `baseline_file` defaulting to `train.py`
- `command`
- `metric_pattern` or parser strategy for `val_bpb`
- optional metadata such as model/provider label, seed, and notes

## Minimal artifact fields

The first artifact should capture:
- `run_id`
- `started_at`, `completed_at`
- `workspace_path`
- `baseline_file`
- `command`
- `exit_code`
- `stdout_path`, `stderr_path`
- `patch_diff`
- `metric`
- `baseline`
- `outcome`
- `failure_reason`
- `runtime_identity`
- `git`
- `system_info` when easily available

## Suggested outcome model

Keep the prototype outcome model small:
- `success_improved`
- `success_regressed`
- `success_no_change`
- `parse_failure`
- `runtime_failure`
- `timeout`
- `invalid_experiment`

This can later map into fuller TraceCore taxonomy if the abstraction proves useful.

## Directory-level outputs

Suggested local output shape:

```text
runs/
  <run_id>/
    artifact.json
    stdout.txt
    stderr.txt
    patch.diff
```

## Hardware and dependency expectations

- **Wrapper + smoke tests**: fine on a laptop/CPU; use tiny commands (e.g., `python metric.py`) to validate the flow.
- **Full `uv run train.py` (autoresearch)**: assumes a single NVIDIA GPU (the repo cites H100). CPU-only or low-end GPUs (e.g., laptop iGPU) will be too slow or fail; expect ~5 minute wall-clock budget per run on supported GPU. Installing the full stack will trigger large torch downloads (2–3 GB for CUDA wheels) plus CUDA toolkit; plan for the bandwidth and disk space.
- **Torch-free shim (current default here)**: we replaced `incubation/autoresearch/autoresearch/train.py` with a CPU-only shim that sleeps and emits a fake, deterministic `val_bpb` (via `--val-bpb`). This avoids torch entirely and is suitable for laptops, but results are synthetic.

## Recommended implementation sequence

1. Create a standalone wrapper script in this directory.
2. Make it work against a local `autoresearch` checkout with fixed inputs.
3. Prove it can reliably capture `train.py` diffs and `val_bpb`.
4. Only after that, evaluate alignment with TraceCore artifact conventions.

## Success criteria for the first prototype

- can run one experiment command reproducibly enough for local comparison
- emits one self-contained artifact folder per run
- reliably classifies basic outcomes
- does not require changes outside the incubation lane
