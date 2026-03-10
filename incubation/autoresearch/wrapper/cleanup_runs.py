from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete wrapper run folders")
    parser.add_argument(
        "--runs-dir",
        default=str(Path(__file__).resolve().parent / "runs"),
        help="Directory containing per-run artifact folders.",
    )
    parser.add_argument(
        "--keep-latest",
        type=int,
        default=0,
        help="Number of most recent runs to keep (by directory mtime).",
    )
    parser.add_argument(
        "--allow-delete-newest",
        action="store_true",
        help="If set, allow deleting the newest run. By default the newest run is always kept as a safety guard.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    runs_dir = Path(args.runs_dir)
    if not runs_dir.exists() or not runs_dir.is_dir():
        print(f"runs directory not found: {runs_dir}")
        return 1

    run_dirs = [p for p in runs_dir.iterdir() if p.is_dir()]
    if not run_dirs:
        print("no run directories found")
        return 0

    run_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    min_keep = max(1, args.keep_latest) if not args.allow_delete_newest else args.keep_latest
    to_delete = run_dirs[min_keep:]

    if not to_delete:
        print(f"nothing to delete; kept latest {min_keep}")
        return 0

    for dir_path in to_delete:
        shutil.rmtree(dir_path, ignore_errors=True)
        print(f"deleted {dir_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
