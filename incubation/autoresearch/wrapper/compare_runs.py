from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two wrapper run artifacts.")
    parser.add_argument(
        "run_ids",
        nargs="*",
        help="Run IDs (directory names) to compare. If omitted, uses the two most recent runs.",
    )
    parser.add_argument(
        "--runs-dir",
        default=str(Path(__file__).resolve().parent / "runs"),
        help="Directory containing per-run artifact folders.",
    )
    return parser.parse_args()


def _load_artifact(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "artifact.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _metric_value(artifact: dict[str, Any]) -> float | None:
    metric = artifact.get("metric") or {}
    value = metric.get("value")
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _pick_runs(runs_dir: Path, requested: list[str]) -> list[Path]:
    candidates = [p for p in runs_dir.iterdir() if p.is_dir()]
    if requested:
        lookup = {p.name: p for p in candidates}
        return [lookup[r] for r in requested if r in lookup]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[:2]


def _format_run(run_dir: Path, artifact: dict[str, Any]) -> str:
    metric_val = _metric_value(artifact)
    baseline_val = (artifact.get("baseline") or {}).get("metric_value")
    outcome = artifact.get("outcome")
    git_commit = (artifact.get("git") or {}).get("commit")
    cmd = artifact.get("command")
    return (
        f"run_id: {artifact.get('run_id')}\n"
        f"  outcome: {outcome}\n"
        f"  metric: {metric_val} (baseline: {baseline_val})\n"
        f"  command: {cmd}\n"
        f"  git: {git_commit}\n"
        f"  dir: {run_dir}\n"
    )


def main() -> int:
    args = _parse_args()
    runs_dir = Path(args.runs_dir)
    if not runs_dir.exists() or not runs_dir.is_dir():
        print(f"runs directory not found: {runs_dir}")
        return 1

    run_dirs = _pick_runs(runs_dir, args.run_ids)
    if len(run_dirs) < 2:
        print("need at least two runs to compare")
        return 1

    artifacts = []
    for run_dir in run_dirs[:2]:
        art = _load_artifact(run_dir)
        if art is None:
            print(f"missing or invalid artifact in {run_dir}")
            return 1
        artifacts.append((run_dir, art))

    (dir_a, art_a), (dir_b, art_b) = artifacts
    metric_a = _metric_value(art_a)
    metric_b = _metric_value(art_b)
    delta = None
    if metric_a is not None and metric_b is not None:
        delta = metric_b - metric_a  # b - a

    print("=== run A (reference) ===")
    print(_format_run(dir_a, art_a))
    print("=== run B (candidate) ===")
    print(_format_run(dir_b, art_b))

    if delta is not None:
        print(f"metric delta (B - A): {delta:+.4f} (lower is better)")
    else:
        print("metric delta: unavailable (missing metric)")

    lineage_a = art_a.get("lineage") or {}
    lineage_b = art_b.get("lineage") or {}
    if lineage_a or lineage_b:
        print("lineage:")
        print(f"  A baseline_run_id: {lineage_a.get('baseline_run_id')}, parent_run_id: {lineage_a.get('parent_run_id')}")
        print(f"  B baseline_run_id: {lineage_b.get('baseline_run_id')}, parent_run_id: {lineage_b.get('parent_run_id')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
