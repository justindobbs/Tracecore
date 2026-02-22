from __future__ import annotations

import pytest

from agent_bench.env.environment import Environment, GuardedEnv, NetworkGuard, SandboxViolation


def _guarded(filesystem_roots: list[str]) -> GuardedEnv:
    return GuardedEnv(
        Environment(),
        allowed_prefixes=("tests.",),
        filesystem_roots=filesystem_roots,
        allow_test_callers=True,
    )


def test_guarded_env_allows_in_root() -> None:
    env = _guarded(["/app"])
    env.write_file("/app/readme.txt", "ok")
    assert env.read_file("/app/readme.txt") == "ok"
    assert env.exists("/app/readme.txt") is True
    assert env.list_dir("/app") == ["/app/readme.txt"]


def test_guarded_env_blocks_outside_root() -> None:
    env = _guarded(["/app"])
    with pytest.raises(SandboxViolation):
        env.write_file("/etc/passwd", "nope")


def test_guarded_env_blocks_when_no_roots() -> None:
    env = _guarded([])
    with pytest.raises(SandboxViolation):
        env.list_dir("/app")


def test_network_guard_allows_literal_and_wildcard() -> None:
    guard = NetworkGuard(["example.com", "*.example.org"])
    guard.check("example.com")
    guard.check("https://api.example.org/v1")
    guard.check("example.com:443")
    with pytest.raises(SandboxViolation):
        guard.check("example.org")
