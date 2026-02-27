"""Tests for agent_bench.integrations.langchain_adapter."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from agent_bench.integrations.langchain_adapter import _build_agent_source, generate_agent
from agent_bench.integrations.llm_shims import BudgetViolation, DeterministicLLMShim, LLMBudget


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

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "langchain"


# ---------------------------------------------------------------------------
# _build_agent_source
# ---------------------------------------------------------------------------

class TestBuildAgentSource:
    def test_is_valid_python(self):
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

    def test_contains_class_and_provider(self):
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

    def test_budget_values_baked_in(self):
        src = _build_agent_source(
            class_name="BudgetAgent",
            task_meta=_FAKE_META,
            model="gpt-4o",
            provider="openai",
            default_fixture=None,
            max_calls=7,
            max_tokens=999,
        )
        assert "max_calls: int = 7" in src
        assert "max_tokens: int = 999" in src

    def test_default_fixture_embedded(self):
        src = _build_agent_source(
            class_name="FixtureAgent",
            task_meta=_FAKE_META,
            model="gpt-4o",
            provider="openai",
            default_fixture="fixtures/my.json",
            max_calls=4,
            max_tokens=2000,
        )
        assert '"fixtures/my.json"' in src

    def test_no_fixture_is_none(self):
        src = _build_agent_source(
            class_name="NoFixtureAgent",
            task_meta=_FAKE_META,
            model="gpt-4o",
            provider="openai",
            default_fixture=None,
            max_calls=4,
            max_tokens=2000,
        )
        assert "_DEFAULT_SHIM_FIXTURE = None" in src

    def test_action_schema_json_present(self):
        src = _build_agent_source(
            class_name="SchemaAgent",
            task_meta=_FAKE_META,
            model="gpt-4o",
            provider="openai",
            default_fixture=None,
            max_calls=4,
            max_tokens=2000,
        )
        assert '"list_dir"' in src
        assert '"set_output"' in src
        assert '"wait"' in src


# ---------------------------------------------------------------------------
# generate_agent — opt-in / opt-out paths
# ---------------------------------------------------------------------------

class TestGenerateAgent:
    def test_writes_file(self, tmp_path: Path):
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

    def test_require_fixture_default_raises_without_fixture(self, tmp_path: Path):
        with pytest.raises(ValueError, match="shim fixture"):
            generate_agent(
                "filesystem_hidden_config@1",
                output_path=tmp_path / "lc_agent.py",
            )

    def test_require_fixture_false_allows_no_fixture(self, tmp_path: Path):
        out = generate_agent(
            "filesystem_hidden_config@1",
            require_fixture=False,
            output_path=tmp_path / "lc_agent.py",
        )
        assert out.exists()

    def test_shim_fixture_path_embedded(self, tmp_path: Path):
        fixture = _FIXTURE_DIR / "filesystem_hidden_config.json"
        out = generate_agent(
            "filesystem_hidden_config@1",
            require_fixture=True,
            shim_fixture=str(fixture),
            output_path=tmp_path / "lc_agent.py",
        )
        src = out.read_text(encoding="utf-8")
        assert "filesystem_hidden_config.json" in src

    def test_budget_derived_from_task_manifest(self, tmp_path: Path):
        out = generate_agent(
            "filesystem_hidden_config@1",
            require_fixture=False,
            output_path=tmp_path / "lc_agent.py",
        )
        src = out.read_text(encoding="utf-8")
        # filesystem_hidden_config default_budget.tool_calls drives max_calls
        assert "max_calls: int = " in src

    def test_custom_class_name(self, tmp_path: Path):
        out = generate_agent(
            "filesystem_hidden_config@1",
            class_name="MyCustomAgent",
            require_fixture=False,
            output_path=tmp_path / "lc_agent.py",
        )
        assert "class MyCustomAgent" in out.read_text(encoding="utf-8")

    def test_log_alert_triage_fixture(self, tmp_path: Path):
        fixture = _FIXTURE_DIR / "log_alert_triage.json"
        out = generate_agent(
            "log_alert_triage@1",
            require_fixture=True,
            shim_fixture=str(fixture),
            output_path=tmp_path / "lc_lat.py",
        )
        src = out.read_text(encoding="utf-8")
        ast.parse(src)
        assert "log_alert_triage" in src


# ---------------------------------------------------------------------------
# DeterministicLLMShim + LLMBudget — unit tests for shim layer
# ---------------------------------------------------------------------------

class TestDeterministicLLMShim:
    def test_key_lookup_returns_response(self):
        shim = DeterministicLLMShim({"openai": '{"type":"wait","args":{}}'})
        result = shim.complete("any prompt", metadata={"response_key": "openai"})
        assert json.loads(result) == {"type": "wait", "args": {}}

    def test_missing_key_raises(self):
        shim = DeterministicLLMShim({"openai": '{"type":"wait","args":{}}'})
        with pytest.raises(KeyError, match="anthropic"):
            shim.complete("prompt", metadata={"response_key": "anthropic"})

    def test_sequence_mode_pops_in_order(self):
        shim = DeterministicLLMShim(['{"type":"list_dir","args":{}}', '{"type":"wait","args":{}}'])
        r1 = shim.complete("p1")
        r2 = shim.complete("p2")
        assert json.loads(r1)["type"] == "list_dir"
        assert json.loads(r2)["type"] == "wait"

    def test_sequence_exhausted_raises(self):
        shim = DeterministicLLMShim(['{"type":"wait","args":{}}'])
        shim.complete("p1")
        with pytest.raises(KeyError, match="exhausted"):
            shim.complete("p2")

    def test_reset_restores_sequence(self):
        shim = DeterministicLLMShim(['{"type":"wait","args":{}}'])
        shim.complete("p1")
        shim.reset()
        result = shim.complete("p1")
        assert json.loads(result)["type"] == "wait"

    def test_from_fixture_loads_file(self, tmp_path: Path):
        fixture = tmp_path / "shim.json"
        fixture.write_text(json.dumps({"openai": '{"type":"wait","args":{}}'}), encoding="utf-8")
        shim = DeterministicLLMShim.from_fixture(fixture)
        result = shim.complete("p", metadata={"response_key": "openai"})
        assert json.loads(result)["type"] == "wait"

    def test_from_fixture_bad_format_raises(self, tmp_path: Path):
        fixture = tmp_path / "bad.json"
        fixture.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON object"):
            DeterministicLLMShim.from_fixture(fixture)

    def test_canonical_fixture_filesystem_hidden_config(self):
        fixture = _FIXTURE_DIR / "filesystem_hidden_config.json"
        shim = DeterministicLLMShim.from_fixture(fixture)
        result = shim.complete("prompt", metadata={"response_key": "openai"})
        action = json.loads(result)
        assert action["type"] == "list_dir"

    def test_canonical_fixture_log_alert_triage(self):
        fixture = _FIXTURE_DIR / "log_alert_triage.json"
        shim = DeterministicLLMShim.from_fixture(fixture)
        result = shim.complete("prompt", metadata={"response_key": "openai"})
        action = json.loads(result)
        assert action["type"] == "list_dir"


# ---------------------------------------------------------------------------
# LLMBudget — budget violation paths
# ---------------------------------------------------------------------------

class TestLLMBudget:
    def test_call_budget_enforced(self):
        budget = LLMBudget(max_calls=2, max_tokens=10000)
        budget.consume("p", "r")
        budget.consume("p", "r")
        with pytest.raises(BudgetViolation, match="call budget"):
            budget.consume("p", "r")

    def test_token_budget_enforced(self):
        budget = LLMBudget(max_calls=100, max_tokens=1)
        with pytest.raises(BudgetViolation, match="token budget"):
            budget.consume("a very long prompt string", "a very long completion string")

    def test_reset_clears_counters(self):
        budget = LLMBudget(max_calls=1, max_tokens=10000)
        budget.consume("p", "r")
        budget.reset()
        budget.consume("p", "r")  # should not raise

    def test_no_limits_never_raises(self):
        budget = LLMBudget()
        for _ in range(100):
            budget.consume("p", "r")

    def test_shim_budget_violation_propagates(self):
        budget = LLMBudget(max_calls=1, max_tokens=10000)
        shim = DeterministicLLMShim(
            {"openai": '{"type":"wait","args":{}}'},
            budget=budget,
        )
        shim.complete("p", metadata={"response_key": "openai"})
        with pytest.raises(BudgetViolation):
            shim.complete("p", metadata={"response_key": "openai"})

    def test_shim_budget_reset_after_episode_reset(self):
        budget = LLMBudget(max_calls=1, max_tokens=10000)
        shim = DeterministicLLMShim(
            {"openai": '{"type":"wait","args":{}}'},
            budget=budget,
        )
        shim.complete("p", metadata={"response_key": "openai"})
        shim.reset()
        # should succeed again after reset
        result = shim.complete("p", metadata={"response_key": "openai"})
        assert json.loads(result)["type"] == "wait"
