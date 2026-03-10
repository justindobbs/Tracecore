from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize wrapper run artifacts.")
    parser.add_argument(
        "--runs-dir",
        default=str(Path(__file__).resolve().parent / "runs"),
        help="Directory containing per-run artifact folders.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of runs to show (sorted by completed_at descending).",
    )
    parser.add_argument(
        "--sort",
        choices=["time", "metric"],
        default="time",
        help="Sort by time (desc) or metric value (asc, missing last).",
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


def _baseline_value(artifact: dict[str, Any]) -> float | None:
    baseline = artifact.get("baseline") or {}
    value = baseline.get("metric_value")
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def main() -> int:
    args = _parse_args()
    runs_dir = Path(args.runs_dir)
    if not runs_dir.exists() or not runs_dir.is_dir():
        print(f"runs directory not found: {runs_dir}")
        return 1

    artifacts = []
    for run_dir in runs_dir.iterdir():
        if not run_dir.is_dir():
            continue
        artifact = _load_artifact(run_dir)
        if artifact is None:
            continue
        artifacts.append((run_dir, artifact))

    if not artifacts:
        print("no artifacts found")
        return 1

    if args.sort == "time":
        artifacts.sort(key=lambda x: x[1].get("completed_at", ""), reverse=True)
    else:
        artifacts.sort(key=lambda x: (_metric_value(x[1]) is None, _metric_value(x[1]) or float("inf")))

    outcome_counter: Counter[str] = Counter()
    metric_values: list[tuple[float, Path, dict[str, Any]]] = []

    for run_dir, artifact in artifacts:
        outcome_counter[artifact.get("outcome", "unknown")] += 1
        metric_val = _metric_value(artifact)
        if metric_val is not None:
            metric_values.append((metric_val, run_dir, artifact))

    total = len(artifacts)
    print(f"found {total} artifacts in {runs_dir}")
    if outcome_counter:
        outcome_str = ", ".join(f"{k}: {v}" for k, v in outcome_counter.most_common())
        print(f"outcome counts -> {outcome_str}")

    if metric_values:
        metric_values.sort(key=lambda t: t[0])
        best_metric, best_dir, best_artifact = metric_values[0]
        print(
            f"best metric (lower is better): {best_metric} from run {best_artifact.get('run_id')} in {best_dir}"
        )

    print("--- runs ---")
    for run_dir, artifact in artifacts[: args.limit]:
        metric_val = _metric_value(artifact)
        baseline_val = _baseline_value(artifact)
        delta = None
        if metric_val is not None and baseline_val is not None:
            delta = metric_val - baseline_val
        delta_str = f" (delta vs baseline: {delta:+.4f})" if delta is not None else ""
        print(
            f"run_id: {artifact.get('run_id')} | outcome: {artifact.get('outcome')} | metric: {metric_val} | "
            f"baseline: {baseline_val}{delta_str} | completed_at: {artifact.get('completed_at')} | dir: {run_dir}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
