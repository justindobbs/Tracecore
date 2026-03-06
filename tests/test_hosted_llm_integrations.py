from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from agent_bench.integrations.langchain_adapter import generate_agent
from agent_bench.runner.runner import run


_HOSTED_CASES = [
    {
        "provider": "openai",
        "model_env": "TRACECORE_HOSTED_OPENAI_MODEL",
        "model_default": "gpt-5-nano",
        "key_env": "OPENAI_API_KEY",
    },
    {
        "provider": "anthropic",
        "model_env": "TRACECORE_HOSTED_ANTHROPIC_MODEL",
        "model_default": "claude-3-5-sonnet-latest",
        "key_env": "ANTHROPIC_API_KEY",
    },
]


pytestmark = pytest.mark.integration


_FAKE_OBSERVATION = {
    "step": 1,
    "last_action": None,
    "last_action_result": None,
    "visible_state": {"files_seen": ["/app/README.md"]},
    "budget_remaining": {"steps": 5, "tool_calls": 5},
}


def _hosted_tests_enabled() -> bool:
    return os.getenv("TRACECORE_RUN_HOSTED_TESTS", "").lower() in {"1", "true", "yes"}


def _load_generated_agent(path: Path):
    spec = importlib.util.spec_from_file_location("hosted_test_agent", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load generated agent from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.LangChainDeterministicAgent


def _provider_ready(case: dict[str, str]) -> bool:
    return bool(os.getenv(case["key_env"]))


def _provider_model(case: dict[str, str]) -> str:
    return os.getenv(case["model_env"], case["model_default"])


def _langchain_core_available() -> bool:
    return importlib.util.find_spec("langchain_core") is not None


@pytest.mark.parametrize("case", _HOSTED_CASES, ids=lambda case: case["provider"])
def test_hosted_langchain_agent_emits_action_and_telemetry(case: dict[str, str], tmp_path: Path):
    if not _hosted_tests_enabled():
        pytest.skip("Set TRACECORE_RUN_HOSTED_TESTS=1 to enable hosted LLM integration tests.")
    if not _provider_ready(case):
        pytest.skip(f"Missing credentials for {case['provider']} hosted test.")

    output_path = tmp_path / f"{case['provider']}_hosted_agent.py"
    generate_agent(
        "filesystem_hidden_config@1",
        provider=case["provider"],
        model=_provider_model(case),
        require_fixture=False,
        shim_fixture=None,
        output_path=output_path,
        max_calls=2,
        max_tokens=2048,
    )

    agent_cls = _load_generated_agent(output_path)
    agent = agent_cls(shim_fixture=None)
    agent.reset({"id": "filesystem_hidden_config", "description": "", "budgets": {"steps": 5, "tool_calls": 5}})
    agent.observe(_FAKE_OBSERVATION)

    action = agent.act()

    assert isinstance(action, dict)
    assert "type" in action
    assert "args" in action
    assert isinstance(action["args"], dict)
    assert action["type"] in {"wait", "list_dir", "read_file", "set_output", "extract_value"}

    assert agent.llm_trace
    telemetry = agent.llm_trace[-1]
    assert telemetry["request"]["provider"] == case["provider"]
    assert telemetry["response"]["provider"] == case["provider"]
    assert telemetry["response"]["model"] == _provider_model(case)
    if telemetry["response"]["success"] is not True:
        pytest.fail(f"Hosted {case['provider']} call failed: {telemetry['response'].get('error')}")
    json.loads(telemetry["response"]["completion"])


def test_hosted_langchain_agent_rejects_unsupported_provider(tmp_path: Path):
    if not _langchain_core_available():
        pytest.skip("langchain-core is not installed in the default test environment.")

    output_path = tmp_path / "unsupported_provider_agent.py"
    generate_agent(
        "filesystem_hidden_config@1",
        provider="unsupported-provider",
        model="demo-model",
        require_fixture=False,
        shim_fixture=None,
        output_path=output_path,
        max_calls=1,
        max_tokens=4096,
    )

    agent_cls = _load_generated_agent(output_path)
    agent = agent_cls(shim_fixture=None)
    agent.observe(_FAKE_OBSERVATION)

    action = agent.act()

    assert action == {"type": "wait", "args": {}}
    assert agent.llm_trace
    telemetry = agent.llm_trace[-1]
    assert telemetry["request"]["provider"] == "unsupported-provider"
    assert telemetry["response"]["success"] is False
    assert "Unsupported provider" in (telemetry["response"].get("error") or "")


@pytest.mark.parametrize("case", _HOSTED_CASES, ids=lambda case: f"runner-{case['provider']}")
def test_hosted_runner_emits_llm_trace_for_deterministic_task(case: dict[str, str], tmp_path: Path):
    if not _hosted_tests_enabled():
        pytest.skip("Set TRACECORE_RUN_HOSTED_TESTS=1 to enable hosted LLM integration tests.")
    if not _provider_ready(case):
        pytest.skip(f"Missing credentials for {case['provider']} hosted test.")

    output_path = tmp_path / f"runner_{case['provider']}_agent.py"
    generate_agent(
        "filesystem_hidden_config@1",
        provider=case["provider"],
        model=_provider_model(case),
        require_fixture=False,
        shim_fixture=None,
        output_path=output_path,
        max_calls=2,
        max_tokens=2048,
    )

    result = run(str(output_path), "filesystem_hidden_config@1", seed=42)

    assert result["task_id"] == "filesystem_hidden_config"
    assert result["version"] == 1
    assert isinstance(result.get("action_trace"), list)
    assert result["termination_reason"] in {"success", "invalid_action", "tool_calls_exhausted", "steps_exhausted"}

    llm_entries = [entry.get("llm_trace") for entry in result["action_trace"] if isinstance(entry, dict)]
    llm_entries = [entry for entry in llm_entries if entry]
    if llm_entries:
        first = llm_entries[0][0]
        assert first["request"]["provider"] == case["provider"]
        assert first["response"]["provider"] == case["provider"]
        assert first["response"]["model"] == _provider_model(case)
        assert "success" in first["response"]
