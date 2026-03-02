"""OTLP export format validation tests.

Verifies that run_to_otlp() and export_otlp_json() produce structurally
valid OTLP ResourceSpans payloads, with the correct TraceCore attribute keys
and taxonomy fields present.
"""

from __future__ import annotations

import json

import pytest

from agent_bench.runner.export_otlp import export_otlp_json, run_to_otlp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(
    *,
    run_id: str = "abc123def456",
    task_ref: str = "filesystem_hidden_config@1",
    agent: str = "agents/toy_agent.py",
    success: bool = True,
    steps: int = 3,
    failure_type: str | None = None,
    termination_reason: str = "success",
) -> dict:
    trace = [
        {
            "step": i + 1,
            "action_ts": "2026-03-01T00:00:00.000000+00:00",
            "action": {"type": "read_file", "args": {"path": "/tmp/file.txt"}},
            "result": {"ok": True},
            "io_audit": [{"type": "fs", "op": "read", "path": "/tmp/file.txt"}],
            "budget_after_step": {"steps": 10 - i, "tool_calls": 20 - i},
            "budget_delta": {"steps": 1, "tool_calls": 1},
        }
        for i in range(steps)
    ]
    return {
        "run_id": run_id,
        "trace_id": f"trace_{run_id}",
        "agent": agent,
        "task_ref": task_ref,
        "task_id": "filesystem_hidden_config",
        "version": 1,
        "seed": 0,
        "harness_version": "1.0.0",
        "started_at": "2026-03-01T00:00:00.000000+00:00",
        "completed_at": "2026-03-01T00:00:01.000000+00:00",
        "success": success,
        "termination_reason": termination_reason,
        "failure_type": failure_type,
        "failure_reason": None,
        "steps_used": steps,
        "tool_calls_used": steps,
        "wall_clock_elapsed_s": 1.0,
        "action_trace": trace,
    }


def _attr_value(span: dict, key: str) -> object | None:
    for attr in span.get("attributes", []):
        if attr.get("key") == key:
            v = attr.get("value", {})
            for vk in ("stringValue", "boolValue", "intValue", "doubleValue"):
                if vk in v:
                    return v[vk]
    return None


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------

def test_run_to_otlp_top_level_keys():
    result = _make_run()
    payload = run_to_otlp(result)
    assert "resourceSpans" in payload
    assert isinstance(payload["resourceSpans"], list)
    assert len(payload["resourceSpans"]) == 1


def test_run_to_otlp_resource_attrs():
    result = _make_run(task_ref="log_stream_monitor@1")
    payload = run_to_otlp(result)
    resource = payload["resourceSpans"][0]["resource"]
    keys = [a["key"] for a in resource.get("attributes", [])]
    assert "service.name" in keys
    assert "tracecore.task_ref" in keys


def test_run_to_otlp_scope_spans_present():
    result = _make_run(steps=2)
    payload = run_to_otlp(result)
    scope_spans = payload["resourceSpans"][0]["scopeSpans"]
    assert len(scope_spans) == 1
    spans = scope_spans[0]["spans"]
    assert len(spans) == 3  # 1 root + 2 step spans


def test_run_to_otlp_root_span_name():
    result = _make_run(task_ref="filesystem_hidden_config@1")
    payload = run_to_otlp(result)
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    root = spans[0]
    assert root["name"] == "episode/filesystem_hidden_config@1"


def test_run_to_otlp_step_span_names():
    result = _make_run(steps=2)
    payload = run_to_otlp(result)
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    step_spans = spans[1:]
    for i, span in enumerate(step_spans):
        assert span["name"].startswith(f"step/{i + 1}/")


def test_run_to_otlp_taxonomy_attrs_on_root():
    result = _make_run(success=False, failure_type="budget_exceeded", termination_reason="budget_exceeded")
    payload = run_to_otlp(result)
    root = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert _attr_value(root, "tracecore.failure_type") == "budget_exceeded"
    assert _attr_value(root, "tracecore.termination_reason") == "budget_exceeded"
    assert _attr_value(root, "tracecore.success") is False


def test_run_to_otlp_success_status_code():
    result = _make_run(success=True)
    payload = run_to_otlp(result)
    root = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert root["status"]["code"] == "STATUS_CODE_OK"


def test_run_to_otlp_failure_status_code():
    result = _make_run(success=False, failure_type="logic_failure")
    payload = run_to_otlp(result)
    root = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert root["status"]["code"] == "STATUS_CODE_ERROR"


def test_run_to_otlp_step_spans_have_parent():
    result = _make_run(steps=2)
    payload = run_to_otlp(result)
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    root_span_id = spans[0]["spanId"]
    for step_span in spans[1:]:
        assert step_span["parentSpanId"] == root_span_id


def test_run_to_otlp_trace_id_consistent():
    result = _make_run(run_id="abc123def456")
    payload = run_to_otlp(result)
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    trace_ids = {s["traceId"] for s in spans}
    assert len(trace_ids) == 1


def test_run_to_otlp_io_audit_attrs():
    result = _make_run(steps=1)
    payload = run_to_otlp(result)
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    step_span = spans[1]
    fs_paths = _attr_value(step_span, "tracecore.io_audit.fs_paths")
    assert fs_paths is not None
    assert "/tmp/file.txt" in fs_paths


# ---------------------------------------------------------------------------
# JSON serialisability
# ---------------------------------------------------------------------------

def test_export_otlp_json_is_valid_json():
    result = _make_run()
    json_str = export_otlp_json(result)
    parsed = json.loads(json_str)
    assert "resourceSpans" in parsed


def test_export_otlp_json_indent():
    result = _make_run()
    json_str = export_otlp_json(result, indent=2)
    assert "\n" in json_str


def test_export_otlp_json_no_indent_compact():
    result = _make_run()
    json_str = export_otlp_json(result)
    assert isinstance(json_str, str)
    json.loads(json_str)  # must be valid


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_run_to_otlp_empty_trace():
    result = _make_run(steps=0)
    result["action_trace"] = []
    payload = run_to_otlp(result)
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 1  # only root span


def test_run_to_otlp_missing_run_id():
    result = _make_run()
    del result["run_id"]
    payload = run_to_otlp(result)
    assert "resourceSpans" in payload


def test_run_to_otlp_step_count_attr():
    result = _make_run(steps=4)
    payload = run_to_otlp(result)
    root = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    count = _attr_value(root, "tracecore.step_count")
    assert count == "4"
