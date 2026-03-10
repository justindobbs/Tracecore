from __future__ import annotations

import argparse
import json
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review emitted autoresearch wrapper artifacts.")
    parser.add_argument(
        "--runs-dir",
        default=str(Path(__file__).resolve().parent / "runs"),
        help="Directory containing per-run artifact folders.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of runs to display.",
    )
    return parser.parse_args()


def _load_artifact(artifact_path: Path) -> dict | None:
    try:
        return json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    args = _parse_args()
    runs_dir = Path(args.runs_dir)
    if not runs_dir.exists() or not runs_dir.is_dir():
        print(f"runs directory not found: {runs_dir}")
        return 1

    run_dirs = sorted((path for path in runs_dir.iterdir() if path.is_dir()), reverse=True)
    shown = 0
    for run_dir in run_dirs:
        artifact = _load_artifact(run_dir / "artifact.json")
        if artifact is None:
            continue
        metric = artifact.get("metric") or {}
        git_info = artifact.get("git") or {}
        print(f"run_id: {artifact.get('run_id')}")
        print(f"  outcome: {artifact.get('outcome')}")
        print(f"  metric: {metric.get('name')}={metric.get('value')}")
        print(f"  command: {artifact.get('command')}")
        print(f"  completed_at: {artifact.get('completed_at')}")
        print(f"  git_commit: {git_info.get('commit')}")
        print(f"  artifact: {run_dir / 'artifact.json'}")
        shown += 1
        if shown >= args.limit:
            break

    if shown == 0:
        print("no readable artifacts found")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
