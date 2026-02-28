"""Tests for --strict-spec compliance mode (spec_check.py)."""

from __future__ import annotations

import copy

import pytest

from agent_bench.runner.runner import run
from agent_bench.runner.spec_check import check_spec_compliance


def _reference_result() -> dict:
    return run("agents/toy_agent.py", "filesystem_hidden_config@1", seed=42)


def test_strict_spec_passes_on_reference_run():
    result = _reference_result()
    report = check_spec_compliance(result)
    assert report["ok"], f"strict-spec failed unexpectedly: {report['errors']}"
    assert report["mode"] == "strict-spec"
    assert report["errors"] == []


def test_strict_spec_result_has_spec_version():
    result = _reference_result()
    assert result.get("spec_version") == "tracecore-spec-v1.0"


def test_strict_spec_result_has_runtime_identity():
    result = _reference_result()
    ri = result.get("runtime_identity")
    assert isinstance(ri, dict)
    assert ri.get("name") == "tracecore"
    assert ri.get("version")


def test_strict_spec_result_has_task_hash():
    result = _reference_result()
    task_hash = result.get("task_hash")
    assert task_hash and task_hash != "unknown", f"task_hash should be a real hash; got {task_hash!r}"


def test_strict_spec_result_has_artifact_hash():
    result = _reference_result()
    artifact_hash = result.get("artifact_hash", "")
    assert artifact_hash.startswith("sha256:"), f"artifact_hash should start with 'sha256:'; got {artifact_hash!r}"


def test_strict_spec_result_has_agent_ref():
    result = _reference_result()
    assert result.get("agent_ref") == "agents/toy_agent.py"


def test_strict_spec_result_has_budgets():
    result = _reference_result()
    budgets = result.get("budgets")
    assert isinstance(budgets, dict)
    assert "steps" in budgets
    assert "tool_calls" in budgets


def test_strict_spec_result_has_wall_clock_elapsed_s():
    result = _reference_result()
    elapsed = result.get("wall_clock_elapsed_s")
    assert elapsed is not None, "wall_clock_elapsed_s should be present"
    assert isinstance(elapsed, (int, float)), f"wall_clock_elapsed_s should be numeric; got {type(elapsed)}"
    assert elapsed >= 0, f"wall_clock_elapsed_s should be non-negative; got {elapsed}"


def test_strict_spec_fails_missing_wall_clock_elapsed_s():
    result = _reference_result()
    del result["wall_clock_elapsed_s"]
    report = check_spec_compliance(result)
    assert not report["ok"]
    assert any("wall_clock_elapsed_s" in e for e in report["errors"])


def test_strict_spec_fails_missing_spec_version():
    result = _reference_result()
    del result["spec_version"]
    report = check_spec_compliance(result)
    assert not report["ok"]
    assert any("spec_version" in e for e in report["errors"])


def test_strict_spec_fails_missing_artifact_hash():
    result = _reference_result()
    del result["artifact_hash"]
    report = check_spec_compliance(result)
    assert not report["ok"]
    assert any("artifact_hash" in e for e in report["errors"])


def test_strict_spec_fails_missing_task_hash():
    result = _reference_result()
    del result["task_hash"]
    report = check_spec_compliance(result)
    assert not report["ok"]
    assert any("task_hash" in e for e in report["errors"])


def test_strict_spec_fails_invalid_failure_type():
    result = _reference_result()
    result["failure_type"] = "nonsense_failure"
    report = check_spec_compliance(result)
    assert not report["ok"]
    assert any("failure_type" in e for e in report["errors"])


def test_strict_spec_fails_missing_runtime_identity():
    result = _reference_result()
    del result["runtime_identity"]
    report = check_spec_compliance(result)
    assert not report["ok"]
    assert any("runtime_identity" in e for e in report["errors"])


def test_strict_spec_fails_trace_entry_missing_field():
    result = _reference_result()
    if result.get("action_trace"):
        bad = copy.deepcopy(result)
        del bad["action_trace"][0]["io_audit"]
        report = check_spec_compliance(bad)
        assert not report["ok"]
        assert any("io_audit" in e for e in report["errors"])
    else:
        pytest.skip("No trace entries to test")
