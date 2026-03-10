# Autoresearch wrapper progress report

## Summary
We now have a CPU-friendly, auditable wrapper for Karpathy’s autoresearch with deterministic shim runs, artifact validation, comparison/report tooling, and passing pytest coverage—all runnable on laptops without torch.

## Recent outcomes
- Shim runs captured (val_bpb 1.05–1.30) with artifacts in `wrapper/runs/`; best run: 1.05 vs baseline 1.5 (success_improved).
- Markdown report generated (`runs_report.md`) showing ranked metrics and deltas.
- Artifact validator confirms 5/5 runs OK.
- Pytest coverage for summarize/compare/report/validate (4 tests passing).

## Tooling completed
- `run_wrapper.py`: seed + lineage recorded; hardware info fixed for Windows; shim-friendly.
- `summarize_runs.py`: outcome filters.
- `compare_runs.py`: baseline override, deltas.
- `report_runs.py`: markdown table (metric/baseline/delta/outcome/git/ts).
- `cleanup_runs.py`: safety guard keeps newest run by default.
- `validate_artifacts.py`: schema sanity checks.

## Usage highlights
- Shim run (CPU): `python run_wrapper.py --workspace-path incubation/autoresearch/autoresearch --command "python train.py --sleep 0.1 --val-bpb 1.11" --baseline-metric 1.50`
- Summaries: `python summarize_runs.py --include-outcomes success_improved success_no_change`
- Compare: `python compare_runs.py --baseline-metric 1.50`
- Report: `python report_runs.py --output runs_report.md`
- Validate: `python validate_artifacts.py`

## Value
- Laptop-ready, no torch download required; deterministic shim metrics for fast iteration.
- Artifacts carry lineage/seed/system info and pass validation.
- Comparison/reporting make regressions/improvements visible without manual log digging.
- Tests guard the CLI utilities for filters, deltas, validation, and reporting.

## CPU laptop example experiment (shim)
- Commands (PowerShell one-liners):
  - `python incubation/autoresearch/wrapper/run_wrapper.py --workspace-path "incubation/autoresearch/autoresearch" --command "python train.py --sleep 0.1 --val-bpb 1.11" --baseline-metric 1.50`
  - `python incubation/autoresearch/wrapper/run_wrapper.py --workspace-path "incubation/autoresearch/autoresearch" --command "python train.py --sleep 0.1 --val-bpb 1.30" --baseline-metric 1.50`
  - `python incubation/autoresearch/wrapper/summarize_runs.py --include-outcomes success_improved success_no_change`
  - `python incubation/autoresearch/wrapper/compare_runs.py --baseline-metric 1.50`
  - `python incubation/autoresearch/wrapper/report_runs.py --output runs_report.md`
- Expected: deterministic metrics ~1.11 and 1.30 vs baseline 1.50 (deltas ≈ -0.39 and -0.20); report ranks runs; validation passes.

## Next (optional)
- Run one GPU-backed `uv run train.py` to validate the full path.
- Add CI hook to run `validate_artifacts.py` + pytest for wrapper utilities.
- Consider a tiny HTML report variant if needed for sharing.
