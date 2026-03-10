import json
import subprocess
import sys
from pathlib import Path


def _make_artifact(dir_path: Path, *, run_id: str, metric: float, baseline: float, outcome: str) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    artifact = {
        "run_id": run_id,
        "started_at": "2026-03-10T00:00:00Z",
        "completed_at": "2026-03-10T00:00:10Z",
        "workspace_path": "./autoresearch",
        "baseline_file": "train.py",
        "command": "python train.py",
        "exit_code": 0,
        "stdout_path": "stdout.txt",
        "stderr_path": "stderr.txt",
        "patch_diff": "",
        "metric": {"name": "val_bpb", "value": metric, "parsed_from": "stdout"},
        "baseline": {"metric_name": "val_bpb", "metric_value": baseline},
        "lineage": {"parent_run_id": None, "baseline_run_id": None},
        "seed": None,
        "outcome": outcome,
        "failure_reason": None,
        "runtime_identity": {"name": "tracecore-autoresearch-wrapper", "version": "0.1.0"},
        "system_info": {"platform": "windows", "machine": "x86_64", "processor": "amd64", "python": "3.10", "cpu_count": "8"},
        "git": {"commit": "abc", "branch": "main"},
        "notes": None,
    }
    (dir_path / "artifact.json").write_text(json.dumps(artifact), encoding="utf-8")


def _run_script(path: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(path), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def test_summarize_filters_by_outcome(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_artifact(runs_dir / "runA", run_id="runA", metric=1.0, baseline=1.5, outcome="success_improved")
    _make_artifact(runs_dir / "runB", run_id="runB", metric=2.0, baseline=1.5, outcome="runtime_failure")

    script = Path(__file__).resolve().parent.parent / "summarize_runs.py"
    proc = _run_script(script, ["--runs-dir", str(runs_dir), "--include-outcomes", "success_improved"], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "runA" in proc.stdout
    assert "runB" not in proc.stdout


def test_compare_runs_baseline_override(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_artifact(runs_dir / "runA", run_id="runA", metric=1.0, baseline=1.5, outcome="success_improved")
    _make_artifact(runs_dir / "runB", run_id="runB", metric=1.2, baseline=1.5, outcome="success_improved")

    script = Path(__file__).resolve().parent.parent / "compare_runs.py"
    proc = _run_script(
        script,
        ["runA", "runB", "--runs-dir", str(runs_dir), "--baseline-metric", "1.50"],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert "baseline override: 1.5" in proc.stdout
    assert "metric delta (B - A): +0.2000" in proc.stdout


def test_validate_artifacts_ok(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_artifact(runs_dir / "runA", run_id="runA", metric=1.0, baseline=1.5, outcome="success_improved")

    script = Path(__file__).resolve().parent.parent / "validate_artifacts.py"
    proc = _run_script(script, ["--runs-dir", str(runs_dir)], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "[OK] runA" in proc.stdout


def test_report_runs_orders_by_metric(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    _make_artifact(runs_dir / "runA", run_id="runA", metric=1.3, baseline=1.5, outcome="success_improved")
    _make_artifact(runs_dir / "runB", run_id="runB", metric=1.1, baseline=1.5, outcome="success_improved")

    script = Path(__file__).resolve().parent.parent / "report_runs.py"
    proc = _run_script(script, ["--runs-dir", str(runs_dir), "--limit", "2"], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    # First data row should contain runB (best metric)
    lines = [line for line in proc.stdout.splitlines() if line.startswith("| run")]
    assert len(lines) >= 3
    assert "runB" in lines[1]
    assert "runA" in lines[2]
