from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_METRIC_REGEX = r"val_bpb\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)"
RUNTIME_NAME = "tracecore-autoresearch-wrapper"
RUNTIME_VERSION = "0.1.0"


def _coerce_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


@dataclass
class MetricResult:
    name: str
    value: float | None
    parsed_from: str | None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wrap an autoresearch experiment run and emit a local artifact.")
    parser.add_argument("--workspace-path", required=True, help="Path to the local autoresearch workspace.")
    parser.add_argument(
        "--command",
        required=True,
        help="Command to execute inside the workspace, e.g. \"uv run train.py\".",
    )
    parser.add_argument(
        "--baseline-file",
        default="train.py",
        help="Relative path to the editable baseline file inside the workspace.",
    )
    parser.add_argument(
        "--runs-dir",
        default=None,
        help="Optional output directory for emitted run artifacts. Defaults to wrapper/runs/.",
    )
    parser.add_argument(
        "--metric-regex",
        default=DEFAULT_METRIC_REGEX,
        help="Regex with one capture group for parsing the metric value from stdout/stderr.",
    )
    parser.add_argument(
        "--metric-name",
        default="val_bpb",
        help="Metric name recorded in the emitted artifact.",
    )
    parser.add_argument(
        "--baseline-metric",
        type=float,
        default=None,
        help="Optional baseline metric for classifying improved/regressed/no-change outcomes.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=None,
        help="Optional process timeout in seconds.",
    )
    parser.add_argument(
        "--notes",
        default=None,
        help="Optional freeform notes to include in the artifact.",
    )
    parser.add_argument(
        "--parent-run-id",
        default=None,
        help="Optional lineage pointer to a prior run (e.g., parent experiment).",
    )
    parser.add_argument(
        "--baseline-run-id",
        default=None,
        help="Optional lineage pointer to the run that supplied the baseline metric.",
    )
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _compute_patch(before: str, after: str, relative_name: str) -> str:
    diff = unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{relative_name}",
        tofile=f"b/{relative_name}",
    )
    return "".join(diff)


def _parse_metric(metric_name: str, metric_regex: str, stdout: str, stderr: str) -> MetricResult:
    pattern = re.compile(metric_regex, re.IGNORECASE)
    for source_name, text in (("stdout", stdout), ("stderr", stderr)):
        matches = pattern.findall(text)
        if not matches:
            continue
        raw = matches[-1]
        if isinstance(raw, tuple):
            raw = raw[0]
        try:
            value = float(raw)
        except ValueError:
            return MetricResult(name=metric_name, value=None, parsed_from=source_name)
        return MetricResult(name=metric_name, value=value, parsed_from=source_name)
    return MetricResult(name=metric_name, value=None, parsed_from=None)


def _classify_outcome(exit_code: int | None, timed_out: bool, metric: MetricResult, baseline_metric: float | None) -> tuple[str, str | None]:
    if timed_out:
        return "timeout", "process timed out"
    if exit_code is None or exit_code != 0:
        return "runtime_failure", f"process_exit_code:{exit_code}"
    if metric.value is None:
        return "parse_failure", "metric_not_found"
    if baseline_metric is None:
        return "success_no_change", None
    if metric.value < baseline_metric:
        return "success_improved", None
    if metric.value > baseline_metric:
        return "success_regressed", None
    return "success_no_change", None


def _runtime_identity() -> dict[str, str]:
    return {
        "name": RUNTIME_NAME,
        "version": RUNTIME_VERSION,
    }


def _system_info() -> dict[str, str]:
    return {
        "platform": platform.platform(),
        "machine": platform.uname().machine,
        "processor": platform.uname().processor,
        "python": sys.version.split()[0],
        "cpu_count": str(platform.cpu_count()),
    }


def _git_value(workspace_path: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            shell=False,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _git_info(workspace_path: Path) -> dict[str, str | None]:
    return {
        "commit": _git_value(workspace_path, "rev-parse", "HEAD"),
        "branch": _git_value(workspace_path, "rev-parse", "--abbrev-ref", "HEAD"),
    }


def _artifact_payload(
    *,
    run_id: str,
    started_at: str,
    completed_at: str,
    workspace_path: Path,
    baseline_file: str,
    command: str,
    exit_code: int | None,
    stdout_path: Path,
    stderr_path: Path,
    patch_diff: str,
    metric: MetricResult,
    outcome: str,
    failure_reason: str | None,
    notes: str | None,
    git_info: dict[str, str | None],
    baseline_metric: float | None,
    parent_run_id: str | None,
    baseline_run_id: str | None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "workspace_path": str(workspace_path),
        "baseline_file": baseline_file,
        "command": command,
        "exit_code": exit_code,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "patch_diff": patch_diff,
        "metric": asdict(metric),
        "baseline": {
            "metric_name": metric.name,
            "metric_value": baseline_metric,
        },
        "lineage": {
            "parent_run_id": parent_run_id,
            "baseline_run_id": baseline_run_id,
        },
        "outcome": outcome,
        "failure_reason": failure_reason,
        "runtime_identity": _runtime_identity(),
        "system_info": _system_info(),
        "git": git_info,
        "notes": notes,
    }


def main() -> int:
    args = _parse_args()
    workspace_path = Path(args.workspace_path).resolve()
    baseline_path = workspace_path / args.baseline_file

    if not workspace_path.exists() or not workspace_path.is_dir():
        raise SystemExit(f"workspace does not exist or is not a directory: {workspace_path}")
    if not baseline_path.exists() or not baseline_path.is_file():
        raise SystemExit(f"baseline file does not exist: {baseline_path}")

    script_dir = Path(__file__).resolve().parent
    runs_root = Path(args.runs_dir).resolve() if args.runs_dir else script_dir / "runs"
    run_id = _run_id()
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    started_at = _now_iso()
    before_text = _read_text(baseline_path)

    stdout_text = ""
    stderr_text = ""
    exit_code: int | None = None
    timed_out = False

    try:
        completed = subprocess.run(
            args.command,
            cwd=str(workspace_path),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=args.timeout_seconds,
        )
        stdout_text = completed.stdout
        stderr_text = completed.stderr
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout_text = _coerce_text(exc.stdout)
        stderr_text = _coerce_text(exc.stderr)
        exit_code = None

    completed_at = _now_iso()
    after_text = _read_text(baseline_path)
    patch_diff = _compute_patch(before_text, after_text, args.baseline_file)
    metric = _parse_metric(args.metric_name, args.metric_regex, stdout_text, stderr_text)
    outcome, failure_reason = _classify_outcome(exit_code, timed_out, metric, args.baseline_metric)
    git_info = _git_info(workspace_path)

    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    diff_path = run_dir / "patch.diff"
    artifact_path = run_dir / "artifact.json"

    _write_text(stdout_path, stdout_text)
    _write_text(stderr_path, stderr_text)
    _write_text(diff_path, patch_diff)

    artifact = _artifact_payload(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        workspace_path=workspace_path,
        baseline_file=args.baseline_file,
        command=args.command,
        exit_code=exit_code,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        patch_diff=patch_diff,
        metric=metric,
        outcome=outcome,
        failure_reason=failure_reason,
        notes=args.notes,
        git_info=git_info,
        baseline_metric=args.baseline_metric,
        parent_run_id=args.parent_run_id,
        baseline_run_id=args.baseline_run_id,
    )
    _write_text(artifact_path, json.dumps(artifact, indent=2) + "\n")

    print(json.dumps({"run_id": run_id, "outcome": outcome, "artifact_path": str(artifact_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
