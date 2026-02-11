"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json

from agent_bench.runner.runner import run


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-bench")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    result = run(args.agent, args.task, seed=args.seed)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
