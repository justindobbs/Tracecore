# Wrapper usage notes

## Run one wrapped experiment

```bash
python incubation/autoresearch/wrapper/run_wrapper.py \
  --workspace-path /path/to/autoresearch \
  --command "uv run train.py" \
  --baseline-metric 1.50
```

### Modes

- **Shim (CPU, default here):** uses the included torch-free `train.py` shim. Runs on laptops, no torch download, emits deterministic fake `val_bpb` via `--val-bpb`.
- **Full autoresearch (GPU):** restore upstream `train.py` and run on a CUDA GPU (repo cites H100). Expect ~5 min per run and large torch/CUDA downloads (~2–3 GB) on first install.

## Review recent emitted runs

```bash
python incubation/autoresearch/wrapper/review_runs.py
```

Quick metric summary:

```bash
python incubation/autoresearch/wrapper/summarize_runs.py
```

Filters:

```bash
python incubation/autoresearch/wrapper/summarize_runs.py --include-outcomes success_improved success_no_change
```

Cleanup old runs (keeps latest N, default 0):

```bash
python incubation/autoresearch/wrapper/cleanup_runs.py --keep-latest 3
python incubation/autoresearch/wrapper/cleanup_runs.py --keep-latest 0 --allow-delete-newest
```

## Example shim smoke test

Run the included torch-free shim and view a summary:

```bash
python incubation/autoresearch/wrapper/run_wrapper.py \
  --workspace-path incubation/autoresearch/autoresearch \
  --command "python train.py --sleep 0.1 --val-bpb 1.11" \
  --baseline-metric 1.50

python incubation/autoresearch/wrapper/summarize_runs.py --limit 5
```

Compare two runs (latest two by default):

```bash
python incubation/autoresearch/wrapper/compare_runs.py
python incubation/autoresearch/wrapper/compare_runs.py 20260310T183743Z-f94ca414 20260310T183753Z-cf17d432
python incubation/autoresearch/wrapper/compare_runs.py --baseline-metric 1.50

Validate artifacts:

```bash
python incubation/autoresearch/wrapper/validate_artifacts.py
```

Generate a markdown report (sorted by metric by default):

```bash
python incubation/autoresearch/wrapper/report_runs.py --output runs_report.md
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

## Expected outputs

Each run produces:
- `artifact.json`
- `stdout.txt`
- `stderr.txt`
- `patch.diff`

under:

```text
incubation/autoresearch/wrapper/runs/<run_id>/
```
