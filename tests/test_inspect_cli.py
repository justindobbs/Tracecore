from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

from agent_bench.cli import _cmd_inspect
from agent_bench.runner import runner


def test_inspect_reads_llm_trace(tmp_path, capsys):
    artifact_path = tmp_path / "artifact.json"
    artifact = {
        "run_id": "abc",
        "task_ref": "demo@1",
        "agent": "agents/demo.py",
        "action_trace": [
            {
                "step": 1,
                "llm_trace": [
                    {
                        "request": {"provider": "openai", "model": "gpt-4o", "prompt": "p", "shim_used": True},
                        "response": {"provider": "openai", "model": "gpt-4o", "shim_used": True, "completion": "{}", "success": True},
                    }
                ],
            }
        ],
    }
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    ns = SimpleNamespace(run=str(artifact_path))
    rc = _cmd_inspect(ns)
    captured = capsys.readouterr()

    assert rc == 0
    assert "llm_trace entries: 1" in captured.out
    assert "openai" in captured.out


def test_runner_disables_llm_trace_via_env(monkeypatch):
    # Stub load_task and load_agent to avoid external dependencies.
    def _stub_task(task_id: str, version: int | None):
        def _setup(seed, env):
            return None

        def _noop():
            return {"ok": True}

        def _validate(env):
            return {"ok": True, "terminal": True}

        return {
            "id": task_id,
            "version": version or 1,
            "description": "stub",
            "default_budget": {"steps": 1, "tool_calls": 1},
            "sandbox": {},
            "setup": SimpleNamespace(setup=_setup),
            "actions": SimpleNamespace(noop=_noop, set_env=lambda env: None),
            "validate": SimpleNamespace(validate=_validate),
        }

    class _StubAgent:
        def __init__(self):
            self.llm_trace = [{"request": {}, "response": {}}]

        def reset(self, task_spec):
            return None

        def observe(self, observation):
            self._obs = observation

        def act(self):
            return {"type": "noop", "args": {}}

    monkeypatch.setenv("AGENT_BENCH_DISABLE_LLM_TRACE", "1")
    monkeypatch.setattr(runner, "load_task", _stub_task)
    monkeypatch.setattr(runner, "load_agent", lambda path: _StubAgent())

    result = runner.run("agents/demo.py", "stub@1", seed=0)
    trace = result.get("action_trace", [])
    assert trace
    assert trace[0].get("llm_trace") is None
