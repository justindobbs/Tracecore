from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a markdown report of recent wrapper runs.")
    parser.add_argument(
        "--runs-dir",
        default=str(Path(__file__).resolve().parent / "runs"),
        help="Directory containing per-run artifact folders.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of runs to include in the report.",
    )
    parser.add_argument(
        "--sort",
        choices=["time", "metric"],
        default="metric",
        help="Sort by time (desc) or metric value (asc, missing last).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output file path for the markdown report. Prints to stdout if not set.",
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


def _delta(metric_val: float | None, baseline_val: float | None) -> float | None:
    if metric_val is None or baseline_val is None:
        return None
    return metric_val - baseline_val


def _format_table(rows: list[dict[str, Any]]) -> str:
    header = "| run_id | metric | baseline | delta | outcome | completed_at | git_commit |\n"
    header += "| --- | --- | --- | --- | --- | --- | --- |\n"
    lines = [header]
    for row in rows:
        lines.append(
            f"| {row['run_id']} | {row['metric']} | {row['baseline']} | {row['delta']} | {row['outcome']} | {row['completed_at']} | {row['git_commit']} |"
        )
    return "\n".join(lines)


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

    rows = []
    for run_dir, artifact in artifacts[: args.limit]:
        metric_val = _metric_value(artifact)
        baseline_val = _baseline_value(artifact)
        delta_val = _delta(metric_val, baseline_val)
        rows.append(
            {
                "run_id": artifact.get("run_id"),
                "metric": metric_val,
                "baseline": baseline_val,
                "delta": f"{delta_val:+.4f}" if delta_val is not None else "n/a",
                "outcome": artifact.get("outcome"),
                "completed_at": artifact.get("completed_at"),
                "git_commit": (artifact.get("git") or {}).get("commit"),
            }
        )

    report_md = "## Autoresearch wrapper runs (sorted by metric)\n\n" + _format_table(rows)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report_md, encoding="utf-8")
        print(f"wrote report to {output_path}")
    else:
        print(report_md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
