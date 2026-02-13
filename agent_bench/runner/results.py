"""Result helpers."""

from __future__ import annotations

from agent_bench.runner.failures import ensure_failure_type


def make_result(**kwargs):
    return ensure_failure_type(dict(**kwargs))
