from __future__ import annotations

import importlib.util

import pytest

from agent_bench.runner.runner import run
from agent_bench.runner.spec_check import check_spec_compliance


def test_fixture_openai_assistants_example_emits_llm_trace_and_passes_strict_spec():
    result = run("examples/openai_assistants_adapter/agents/fixture_openai_assistants_agent.py", "filesystem_hidden_config@1", seed=0)

    report = check_spec_compliance(result)
    assert report["ok"], report["errors"]
    assert result["success"] is True

    traces = []
    for step in result.get("action_trace") or []:
        traces.extend(step.get("llm_trace") or [])
    assert traces
    assert traces[0]["request"]["provider"] == "openai"
    assert traces[0]["request"]["metadata"]["surface"] == "assistants"
    assert traces[0]["response"]["success"] is True
