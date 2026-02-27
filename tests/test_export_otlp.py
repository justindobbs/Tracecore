"""Tests for agent_bench.runner.export_otlp."""

from __future__ import annotations

import json

import pytest

from agent_bench.runner.export_otlp import (
    _iso_to_unix_nano,
    _make_attribute,
    _run_id_to_trace_id,
    _step_to_span_id,
    export_otlp_json,
    run_to_otlp,
)


_MINIMAL_RUN = {
    "run_id": "abcdef1234567890abcdef1234567890",
    "trace_id": "abcdef1234567890abcdef1234567890",
    "agent": "agents/toy_agent.py",
    "task_ref": "filesystem_hidden_config@1",
    "task_id": "filesystem_hidden_config",
    "version": 1,
    "seed": 0,
    "harness_version": "0.9.8",
    "started_at": "2026-02-20T19:00:00.000000+00:00",
    "completed_at": "2026-02-20T19:00:01.000000+00:00",
    "success": True,
    "termination_reason": "success",
    "failure_type": None,
    "failure_reason": None,
    "steps_used": 2,
    "tool_calls_used": 2,
    "metrics": {"steps_used": 2, "tool_calls_used": 2},
    "action_trace": [
        {
            "step": 1,
            "action_ts": "2026-02-20T19:00:00.100000+00:00",
            "action": {"type": "list_dir", "args": {"path": "."}},
            "result": {"ok": True, "files": ["config"]},
            "io_audit": [{"type": "fs", "op": "list_dir", "path": "/app"}],
            "budget_after_step": {"steps": 9, "tool_calls": 9},
            "budget_delta": {"steps": 1, "tool_calls": 1},
        },
        {
            "step": 2,
            "action_ts": "2026-02-20T19:00:00.500000+00:00",
            "action": {"type": "set_output", "args": {"key": "API_KEY", "value": "secret"}},
            "result": {"ok": True},
            "io_audit": [],
            "budget_after_step": {"steps": 8, "tool_calls": 8},
            "budget_delta": {"steps": 1, "tool_calls": 1},
        },
    ],
}


def test_iso_to_unix_nano_basic():
    ns = _iso_to_unix_nano("2026-02-20T19:00:00.000000+00:00")
    assert ns > 0
    assert isinstance(ns, int)


def test_iso_to_unix_nano_bad_returns_zero():
    assert _iso_to_unix_nano("not-a-date") == 0


def test_make_attribute_types():
    assert _make_attribute("k", True) == {"key": "k", "value": {"boolValue": True}}
    assert _make_attribute("k", 42) == {"key": "k", "value": {"intValue": "42"}}
    assert _make_attribute("k", 3.14) == {"key": "k", "value": {"doubleValue": 3.14}}
    assert _make_attribute("k", "hello") == {"key": "k", "value": {"stringValue": "hello"}}
    assert _make_attribute("k", None) == {"key": "k", "value": {"stringValue": ""}}
    assert _make_attribute("k", {"a": 1}) == {"key": "k", "value": {"stringValue": '{"a": 1}'}}


def test_run_id_to_trace_id_padding():
    short = _run_id_to_trace_id("abc")
    assert len(short) == 32
    assert short.startswith("abc")
    assert all(c in "0123456789abcdefABCDEF" for c in short)


def test_run_id_to_trace_id_truncation():
    long_id = "a" * 64
    assert len(_run_id_to_trace_id(long_id)) == 32


def test_step_to_span_id_format():
    sid = _step_to_span_id("abcdef1234567890", 1)
    assert len(sid) == 16
    assert all(c in "0123456789abcdef" for c in sid)


def test_run_to_otlp_structure():
    payload = run_to_otlp(_MINIMAL_RUN)
    assert "resourceSpans" in payload
    rs = payload["resourceSpans"]
    assert len(rs) == 1
    scope_spans = rs[0]["scopeSpans"]
    assert len(scope_spans) == 1
    spans = scope_spans[0]["spans"]
    assert len(spans) == 3  # 1 root + 2 step spans
    assert spans[0]["name"].startswith("episode/")
    assert spans[1]["name"].startswith("step/1/")
    assert spans[2]["name"].startswith("step/2/")


def test_run_to_otlp_root_span_attributes():
    payload = run_to_otlp(_MINIMAL_RUN)
    root_span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    attr_keys = {a["key"] for a in root_span["attributes"]}
    assert "tracecore.run_id" in attr_keys
    assert "tracecore.task_ref" in attr_keys
    assert "tracecore.success" in attr_keys
    assert "tracecore.termination_reason" in attr_keys
    assert "tracecore.failure_type" in attr_keys
    assert "tracecore.steps_used" in attr_keys


def test_run_to_otlp_step_span_io_audit():
    payload = run_to_otlp(_MINIMAL_RUN)
    step1_span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
    attr_keys = {a["key"] for a in step1_span["attributes"]}
    assert "tracecore.io_audit.fs_paths" in attr_keys


def test_run_to_otlp_parent_linkage():
    payload = run_to_otlp(_MINIMAL_RUN)
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    root_id = spans[0]["spanId"]
    for step_span in spans[1:]:
        assert step_span["parentSpanId"] == root_id


def test_run_to_otlp_no_trace():
    run = dict(_MINIMAL_RUN)
    run["action_trace"] = []
    payload = run_to_otlp(run)
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 1  # only root span


def test_run_to_otlp_failure_status():
    run = dict(_MINIMAL_RUN)
    run["success"] = False
    run["termination_reason"] = "steps_exhausted"
    run["failure_type"] = "budget_exhausted"
    payload = run_to_otlp(run)
    root_span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert root_span["status"]["code"] == "STATUS_CODE_ERROR"


def test_export_otlp_json_is_valid_json():
    s = export_otlp_json(_MINIMAL_RUN)
    parsed = json.loads(s)
    assert "resourceSpans" in parsed


def test_export_otlp_json_indented():
    s = export_otlp_json(_MINIMAL_RUN, indent=2)
    assert "\n" in s


def test_run_to_otlp_resource_attributes():
    payload = run_to_otlp(_MINIMAL_RUN)
    res_attrs = {a["key"] for a in payload["resourceSpans"][0]["resource"]["attributes"]}
    assert "service.name" in res_attrs
    assert "tracecore.task_ref" in res_attrs
