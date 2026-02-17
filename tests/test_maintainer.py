from __future__ import annotations

from pathlib import Path

from agent_bench.maintainer import suggest_fix_pydantic_agent_import
from agent_bench.maintainer import maintain
from agent_bench.maintainer import apply_fix


def test_suggest_fix_pydantic_agent_import_aliases_agent_import() -> None:
    src = """\
from pydantic_ai import Agent, RunContext

class Foo:
    pass
"""
    changed, updated = suggest_fix_pydantic_agent_import(src)
    assert changed is True
    assert "from pydantic_ai import Agent as PydanticAgent, RunContext" in updated


def test_suggest_fix_pydantic_agent_import_noop_when_absent() -> None:
    src = """\
import random

class Agent:
    def reset(self, task_spec):
        pass
"""
    changed, updated = suggest_fix_pydantic_agent_import(src)
    assert changed is False
    assert updated == src


def test_maintain_fails_when_fix_target_missing(tmp_path) -> None:
    payload = maintain(
        cwd=tmp_path,
        pytest_args=["-q"],
        validate_tasks=False,
        fix_agent_files=["missing_agent.py"],
        dry_run=True,
    )
    assert payload["ok"] is False
    assert payload["fix_errors"] == 1


def test_apply_fix_rewrites_pydantic_agent_import(tmp_path) -> None:
    sample = Path(__file__).parent / "sample_agents" / "needs_fix_pydantic_import.py"
    target = tmp_path / "needs_fix_pydantic_import.py"
    target.write_text(sample.read_text(encoding="utf-8"), encoding="utf-8")

    res = apply_fix(target, dry_run=False)
    assert res["changed"] is True

    updated = target.read_text(encoding="utf-8")
    assert "from pydantic_ai import Agent as PydanticAgent, RunContext" in updated
