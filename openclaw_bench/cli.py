"""CLI entrypoint (stub)."""

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(prog="openclaw-bench")
    parser.add_argument("--agent")
    parser.add_argument("--task")
    parser.add_argument("--seed", type=int, default=0)
    _args = parser.parse_args()
    raise SystemExit("Runner not implemented yet.")


if __name__ == "__main__":
    raise SystemExit(main())
