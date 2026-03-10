from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

REQUIRED_TOP_LEVEL = [
    "run_id",
    "started_at",
    "completed_at",
    "workspace_path",
    "baseline_file",
    "command",
    "exit_code",
    "stdout_path",
    "stderr_path",
    "patch_diff",
    "metric",
    "baseline",
    "outcome",
    "runtime_identity",
    "git",
    "system_info",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate wrapper artifact JSON files")
    parser.add_argument(
        "--runs-dir",
        default=str(Path(__file__).resolve().parent / "runs"),
        help="Directory containing per-run artifact folders.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on first error (default is to report all).",
    )
    return parser.parse_args()


def _load_artifact(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _check_required(obj: dict[str, Any], keys: Iterable[str]) -> list[str]:
    missing = []
    for key in keys:
        if key not in obj:
            missing.append(key)
    return missing


def _is_floatish(value: Any) -> bool:
    try:
        float(value)
        return True
    except Exception:
        return False


def _validate_artifact(path: Path) -> list[str]:
    errors: list[str] = []
    art = _load_artifact(path)
    if art is None:
        return ["invalid JSON"]

    missing = _check_required(art, REQUIRED_TOP_LEVEL)
    if missing:
        errors.append(f"missing top-level keys: {', '.join(missing)}")

    metric = art.get("metric") or {}
    if not _is_floatish(metric.get("value")):
        errors.append("metric.value missing or not a number")

    baseline = art.get("baseline") or {}
    if "metric_value" in baseline and baseline.get("metric_value") is not None and not _is_floatish(
        baseline.get("metric_value")
    ):
        errors.append("baseline.metric_value not numeric")

    lineage = art.get("lineage") or {}
    if lineage and not isinstance(lineage, dict):
        errors.append("lineage should be an object")

    system_info = art.get("system_info") or {}
    required_sys = ["platform", "python"]
    missing_sys = _check_required(system_info, required_sys)
    if missing_sys:
        errors.append(f"system_info missing: {', '.join(missing_sys)}")

    runtime_identity = art.get("runtime_identity") or {}
    for key in ("name", "version"):
        if key not in runtime_identity:
            errors.append(f"runtime_identity missing {key}")

    return errors


def main() -> int:
    args = _parse_args()
    runs_dir = Path(args.runs_dir)
    if not runs_dir.exists() or not runs_dir.is_dir():
        print(f"runs directory not found: {runs_dir}")
        return 1

    any_errors = False
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        artifact_path = run_dir / "artifact.json"
        if not artifact_path.exists():
            continue
        errors = _validate_artifact(artifact_path)
        if errors:
            any_errors = True
            print(f"[FAIL] {run_dir.name}: {', '.join(errors)}")
            if args.strict:
                return 1
        else:
            print(f"[OK] {run_dir.name}")

    return 1 if any_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
