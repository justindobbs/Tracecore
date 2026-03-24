from __future__ import annotations

import importlib.util
import pytest

from agent_bench.runner.runner import run
from agent_bench.runner.spec_check import check_spec_compliance


def test_fixture_langchain_example_emits_llm_trace_and_passes_strict_spec():
    if importlib.util.find_spec("langchain_core") is None:
        pytest.skip("langchain-core is not installed in the default test environment.")
    result = run("examples/langchain_adapter/agents/fixture_langchain_agent.py", "filesystem_hidden_config@1", seed=0)

    report = check_spec_compliance(result)
    assert report["ok"], report["errors"]
    assert result["success"] is True
    assert result["failure_type"] is None
    assert result["spec_version"] == "tracecore-spec-v1.0"

    trace = result["action_trace"]
    assert trace
    llm_entries = []
    for step in trace:
        llm_entries.extend(step.get("llm_trace") or [])
    assert llm_entries
    first = llm_entries[0]
    assert first["request"]["provider"] == "openai"
    assert first["response"]["model"] == "gpt-4o-mini"
    assert first["response"]["success"] is True
