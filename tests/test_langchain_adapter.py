"""Tests for agent_bench.integrations.langchain_adapter."""

from __future__ import annotations

import ast
from pathlib import Path

from agent_bench.integrations.langchain_adapter import _build_agent_source, generate_agent


_FAKE_META = {
    "task_id": "demo_task",
    "version": 1,
    "description": "Demo task for LangChain adapters.",
    "action_schema": {
        "wait": [],
        "set_output": ["key", "value"],
        "list_dir": [],
    },
    "default_budget": {"steps": 3, "tool_calls": 3},
}


def test_build_agent_source_is_valid_python():
    src = _build_agent_source(
        class_name="DeterministicLCAdapter",
        task_meta=_FAKE_META,
        model="gpt-4o-mini",
        provider="openai",
        default_fixture="fixtures/lc.json",
        max_calls=4,
        max_tokens=2000,
    )
    ast.parse(src)
    assert "LLMCallTelemetry" in src
    assert "llm_trace" in src


def test_build_agent_source_contains_schema_and_prompt():
    src = _build_agent_source(
        class_name="LCShimAgent",
        task_meta=_FAKE_META,
        model="claude-3",
        provider="anthropic",
        default_fixture=None,
        max_calls=2,
        max_tokens=512,
    )
    assert "class LCShimAgent" in src
    assert "anthropic" in src
    assert "claude-3" in src
    assert "set_output" in src
    assert "LangChain-backed adapter" in src


def test_generate_agent_writes_file(tmp_path: Path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        require_fixture=False,
        shim_fixture=None,
        output_path=tmp_path / "lc_agent.py",
    )
    assert out.exists()
    src = out.read_text(encoding="utf-8")
    ast.parse(src)
    assert "LangChainDeterministicAgent" in src
    assert "filesystem_hidden_config" in src


def test_generated_source_includes_llm_trace(tmp_path: Path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        require_fixture=False,
        shim_fixture=None,
        output_path=tmp_path / "lc_agent.py",
    )
    text = out.read_text(encoding="utf-8")
    assert "llm_trace" in text
    assert "LLMCallTelemetry" in text
