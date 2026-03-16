"""Golden run artifact schema assertions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_bench.runner import runner as runner_mod
from agent_bench.runner.runner import run


REQUIRED_TOP_LEVEL = {
    "run_id",
    "trace_id",
    "agent",
    "agent_ref",
    "task_ref",
    "task_id",
    "task_hash",
    "version",
    "seed",
    "success",
    "failure_type",
    "failure_reason",
    "termination_reason",
    "steps_used",
    "tool_calls_used",
    "harness_version",
    "spec_version",
    "runtime_identity",
    "budgets",
    "artifact_hash",
    "started_at",
    "completed_at",
    "wall_clock_elapsed_s",
    "sandbox",
    "evidence_links",
    "action_trace",
}

TRACE_ENTRY_FIELDS = {
    "step",
    "action_ts",
    "observation",
    "action",
    "result",
    "io_audit",
    "budget_after_step",
    "budget_delta",
}

OBSERVATION_FIELDS = {"step", "task", "budget_remaining"}


def _run_reference() -> dict:
    return run("agents/toy_agent.py", "filesystem_hidden_config@1", seed=42)


def test_run_artifact_includes_required_fields():
    result = _run_reference()
    missing = REQUIRED_TOP_LEVEL.difference(result.keys())
    assert not missing, f"missing keys: {sorted(missing)}"
    assert isinstance(result["action_trace"], list) and result["action_trace"], "action_trace should be non-empty"


def test_action_trace_entries_capture_budget_and_audit_fields():
    result = _run_reference()
    entry = result["action_trace"][0]
    missing = TRACE_ENTRY_FIELDS.difference(entry.keys())
    assert not missing, f"trace entry missing keys: {sorted(missing)}"
    assert isinstance(entry["io_audit"], list)
    obs = entry["observation"]
    missing_obs = OBSERVATION_FIELDS.difference(obs.keys())
    assert not missing_obs, f"observation missing keys: {sorted(missing_obs)}"


def test_action_trace_entries_include_action_metrics_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("TRACECORE_ACTION_METRICS_VERBOSITY", raising=False)
    result = _run_reference()
    telemetry = result["action_trace"][0].get("telemetry")
    assert isinstance(telemetry, dict)
    action_metrics = telemetry.get("action_metrics")
    assert isinstance(action_metrics, dict)
    assert isinstance(action_metrics.get("latency_ms"), (int, float))
    assert action_metrics["latency_ms"] >= 0
    assert "error" in action_metrics
    assert "tool_call" not in action_metrics


def test_action_trace_entries_include_verbose_action_metric_fields(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRACECORE_ACTION_METRICS_VERBOSITY", "verbose")
    result = _run_reference()
    action_metrics = result["action_trace"][0]["telemetry"]["action_metrics"]
    assert action_metrics["tool_call"] is True


def test_action_trace_entries_disable_action_metrics_when_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRACECORE_ACTION_METRICS_VERBOSITY", "off")
    result = _run_reference()
    telemetry = result["action_trace"][0].get("telemetry")
    assert isinstance(telemetry, dict)
    assert telemetry.get("action_metrics") is None


def test_run_artifact_runtime_metadata_has_expected_shape():
    result = _run_reference()
    runtime_identity = result["runtime_identity"]
    assert isinstance(runtime_identity, dict)
    assert runtime_identity["name"] == "tracecore"
    assert isinstance(runtime_identity.get("version"), str) and runtime_identity["version"]
    assert "git_sha" in runtime_identity

    budgets = result["budgets"]
    assert isinstance(budgets, dict)
    assert isinstance(budgets.get("steps"), int)
    assert isinstance(budgets.get("tool_calls"), int)

    artifact_hash = result["artifact_hash"]
    assert isinstance(artifact_hash, str)
    assert artifact_hash.startswith("sha256:")

    evidence_links = result["evidence_links"]
    assert evidence_links == {"bundle_dir": None, "bundle_manifest": None}


def test_failure_artifact_preserves_failure_invariants():
    result = run("agents/cheater_agent.py", "filesystem_hidden_config@1", seed=42)
    assert result["success"] is False
    assert isinstance(result["failure_type"], str) and result["failure_type"]
    assert isinstance(result["termination_reason"], str) and result["termination_reason"]
    assert result["failure_reason"] is not None
    assert isinstance(result["action_trace"], list)
    assert result["artifact_hash"].startswith("sha256:")


def test_action_trace_llm_telemetry_shape(monkeypatch: pytest.MonkeyPatch):
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
            "sandbox": {"filesystem_roots": ["/app"], "network_hosts": []},
            "setup": SimpleNamespace(setup=_setup),
            "actions": SimpleNamespace(noop=_noop, set_env=lambda env: None),
            "validate": SimpleNamespace(validate=_validate),
        }

    class _TelemetryAgent:
        def __init__(self):
            self.llm_trace = [
                {
                    "request": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "prompt": "hello",
                        "shim_used": True,
                    },
                    "response": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "shim_used": True,
                        "completion": "{}",
                        "success": True,
                        "error": None,
                        "calls_used": 1,
                        "tokens_used": 12,
                        "timestamp": "2026-03-06T00:00:00.000000+00:00",
                    },
                }
            ]

        def reset(self, task_spec):
            return None

        def observe(self, observation):
            self._obs = observation

        def act(self):
            return {"type": "noop", "args": {}}

    monkeypatch.delenv("AGENT_BENCH_DISABLE_LLM_TRACE", raising=False)
    monkeypatch.setattr(runner_mod, "load_task", _stub_task)
    monkeypatch.setattr(runner_mod, "load_agent", lambda path: _TelemetryAgent())

    result = runner_mod.run("agents/demo.py", "stub@1", seed=0)
    trace = result["action_trace"]
    assert trace
    llm_trace = trace[0].get("llm_trace")
    assert isinstance(llm_trace, list) and llm_trace
    first = llm_trace[0]
    assert first["request"]["provider"] == "openai"
    assert first["request"]["model"] == "gpt-4o-mini"
    assert first["response"]["success"] is True
    assert first["response"]["tokens_used"] == 12


def test_run_artifact_wall_clock_elapsed_is_numeric_for_reference_run():
    result = _run_reference()
    elapsed = result["wall_clock_elapsed_s"]
    assert isinstance(elapsed, (int, float))
    assert elapsed >= 0


def test_reasoning_benchmark_is_absent_by_default(monkeypatch: pytest.MonkeyPatch):
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
            "sandbox": {"filesystem_roots": ["/app"], "network_hosts": []},
            "setup": SimpleNamespace(setup=_setup),
            "actions": SimpleNamespace(noop=_noop, set_env=lambda env: None),
            "validate": SimpleNamespace(validate=_validate),
        }

    class _Agent:
        def reset(self, task_spec):
            return None

        def observe(self, observation):
            self._obs = observation

        def act(self):
            return {"type": "noop", "args": {}}

    monkeypatch.delenv("TRACECORE_ENABLE_REASONING_BENCHMARK", raising=False)
    monkeypatch.setattr(runner_mod, "load_task", _stub_task)
    monkeypatch.setattr(runner_mod, "load_agent", lambda path: _Agent())

    result = runner_mod.run("agents/demo.py", "stub@1", seed=0)

    assert "reasoning_benchmark" not in result


def test_reasoning_benchmark_is_emitted_when_enabled(monkeypatch: pytest.MonkeyPatch):
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
            "sandbox": {"filesystem_roots": ["/app"], "network_hosts": []},
            "reasoning_rubric": {
                "id": "answer_quality",
                "version": 1,
                "criteria": [
                    {"id": "correctness", "description": "Answer is correct", "weight": 1.0},
                ],
            },
            "setup": SimpleNamespace(setup=_setup),
            "actions": SimpleNamespace(noop=_noop, set_env=lambda env: None),
            "validate": SimpleNamespace(validate=_validate),
        }

    class _ReasoningAgent:
        reasoning_judge_provider = "manual"
        reasoning_judge_adapter = "baseline"
        reasoning_judge_summary = "ready_for_judge"

        def reset(self, task_spec):
            self.llm_trace = [{"request": {"provider": "openai"}, "response": {"success": True}}]
            return None

        def observe(self, observation):
            self._obs = observation

        def act(self):
            return {"type": "noop", "args": {}}

    monkeypatch.delenv("TRACECORE_ENABLE_REASONING_BENCHMARK", raising=False)
    monkeypatch.setattr(runner_mod, "load_task", _stub_task)
    monkeypatch.setattr(runner_mod, "load_agent", lambda path: _ReasoningAgent())

    result = runner_mod.run("agents/demo.py", "stub@1", seed=0, enable_reasoning_benchmark=True)

    benchmark = result.get("reasoning_benchmark")
    assert isinstance(benchmark, dict)
    assert benchmark["enabled"] is True
    assert benchmark["judge"]["adapter"] == "baseline"
    assert benchmark["judge"]["provider"] == "manual"
    assert benchmark["rubric"]["id"] == "answer_quality"
    assert benchmark["rubric"]["version"] == 1
    assert benchmark["rubric"]["criteria"][0]["id"] == "correctness"
    assert benchmark["trace_summary"]["steps_observed"] == 1
    assert benchmark["trace_summary"]["has_llm_trace"] is True
    assert benchmark["result"]["status"] == "not_evaluated"
    assert benchmark["result"]["summary"] == "ready_for_judge"
