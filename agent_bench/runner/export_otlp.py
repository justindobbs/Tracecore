"""Structured trace export in OTLP-compatible JSON format.

Converts a TraceCore run artifact into an OpenTelemetry Protocol (OTLP)
Traces JSON payload that downstream monitoring pipelines can ingest without
manual patching.

The mapping is::

    run  ->  ResourceSpans
      episode (root span)  ->  one Span per run
        each trace entry   ->  one child Span per step

Span attributes carry the full TraceCore taxonomy so failure type,
termination reason, and budget deltas are queryable in any OTLP-compatible
backend (Grafana Tempo, Jaeger, Honeycomb, etc.).

Usage::

    from agent_bench.runner.export_otlp import run_to_otlp
    payload = run_to_otlp(result)          # dict ready for json.dumps
    json_str = export_otlp_json(result)    # convenience wrapper
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any


_SCHEMA_URL = "https://opentelemetry.io/schemas/1.21.0"
_INSTRUMENTATION_SCOPE = "agent_bench.tracecore"


def _iso_to_unix_nano(ts: str) -> int:
    """Parse an ISO 8601 timestamp string and return Unix nanoseconds."""
    ts = ts.rstrip("Z")
    if "+" in ts:
        ts = ts.split("+")[0]
    try:
        dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    return int(dt.timestamp() * 1_000_000_000)


def _make_attribute(key: str, value: Any) -> dict:
    """Wrap a key/value pair as an OTLP AnyValue attribute."""
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    if isinstance(value, dict):
        return {"key": key, "value": {"stringValue": json.dumps(value, ensure_ascii=False)}}
    if isinstance(value, list):
        return {"key": key, "value": {"stringValue": json.dumps(value, ensure_ascii=False)}}
    return {"key": key, "value": {"stringValue": str(value) if value is not None else ""}}


def _run_id_to_trace_id(run_id: str) -> str:
    """Pad/truncate a run_id hex string to 32 hex chars (128-bit trace ID)."""
    clean = re.sub(r"[^0-9a-fA-F]", "", run_id or "")
    return clean[:32].ljust(32, "0")


def _step_to_span_id(run_id: str, step: int) -> str:
    """Derive a stable 16-char (64-bit) span ID from run_id + step."""
    clean = re.sub(r"[^0-9a-fA-F]", "", run_id or "")
    base = clean[:12].ljust(12, "0")
    return base + format(step & 0xFFFF, "04x")


def _root_span_id(run_id: str) -> str:
    clean = re.sub(r"[^0-9a-fA-F]", "", run_id or "")
    return clean[:16].ljust(16, "0")


def _step_span(entry: dict, run_id: str, trace_id: str, root_span_id: str) -> dict:
    step = entry.get("step", 0)
    action = entry.get("action") or {}
    result = entry.get("result") or {}
    io_audit = entry.get("io_audit") or []
    budget_after = entry.get("budget_after_step") or {}
    budget_delta = entry.get("budget_delta") or {}

    action_ts = entry.get("action_ts", "")
    start_nano = _iso_to_unix_nano(action_ts)
    end_nano = start_nano + 1_000_000  # 1ms default duration for step spans

    attributes = [
        _make_attribute("tracecore.step", step),
        _make_attribute("tracecore.action.type", action.get("type", "")),
        _make_attribute("tracecore.action.args", json.dumps(action.get("args", {}), ensure_ascii=False)),
        _make_attribute("tracecore.result.ok", bool(result.get("ok", True))),
        _make_attribute("tracecore.budget.steps_remaining", budget_after.get("steps", 0)),
        _make_attribute("tracecore.budget.tool_calls_remaining", budget_after.get("tool_calls", 0)),
        _make_attribute("tracecore.budget.steps_delta", budget_delta.get("steps", 1)),
        _make_attribute("tracecore.budget.tool_calls_delta", budget_delta.get("tool_calls", 1)),
        _make_attribute("tracecore.io_audit.count", len(io_audit)),
    ]

    fs_paths = [a.get("path", "") for a in io_audit if a.get("type") == "fs"]
    net_hosts = [a.get("host", "") for a in io_audit if a.get("type") == "net"]
    if fs_paths:
        attributes.append(_make_attribute("tracecore.io_audit.fs_paths", json.dumps(fs_paths)))
    if net_hosts:
        attributes.append(_make_attribute("tracecore.io_audit.net_hosts", json.dumps(net_hosts)))

    status_code = "STATUS_CODE_OK" if result.get("ok", True) else "STATUS_CODE_ERROR"

    return {
        "traceId": trace_id,
        "spanId": _step_to_span_id(run_id, step),
        "parentSpanId": root_span_id,
        "name": f"step/{step}/{action.get('type', 'unknown')}",
        "kind": 1,
        "startTimeUnixNano": str(start_nano),
        "endTimeUnixNano": str(end_nano),
        "attributes": attributes,
        "status": {"code": status_code},
    }


def _root_span(result: dict, trace_id: str, root_span_id: str, child_spans: list[dict]) -> dict:
    run_id = result.get("run_id", "")
    started_at = result.get("started_at", "")
    completed_at = result.get("completed_at", "")
    start_nano = _iso_to_unix_nano(started_at)
    end_nano = _iso_to_unix_nano(completed_at) if completed_at else start_nano + 1_000_000

    success = bool(result.get("success"))
    failure_type = result.get("failure_type") or ""
    termination_reason = result.get("termination_reason") or ""
    failure_reason = result.get("failure_reason") or ""

    attributes = [
        _make_attribute("tracecore.run_id", run_id),
        _make_attribute("tracecore.task_ref", result.get("task_ref", "")),
        _make_attribute("tracecore.task_id", result.get("task_id", "")),
        _make_attribute("tracecore.version", result.get("version", 0)),
        _make_attribute("tracecore.seed", result.get("seed", 0)),
        _make_attribute("tracecore.agent", result.get("agent", "")),
        _make_attribute("tracecore.harness_version", result.get("harness_version", "")),
        _make_attribute("tracecore.success", success),
        _make_attribute("tracecore.termination_reason", termination_reason),
        _make_attribute("tracecore.failure_type", failure_type),
        _make_attribute("tracecore.failure_reason", failure_reason),
        _make_attribute("tracecore.steps_used", result.get("steps_used", 0)),
        _make_attribute("tracecore.tool_calls_used", result.get("tool_calls_used", 0)),
        _make_attribute("tracecore.step_count", len(result.get("action_trace", []))),
    ]

    status_code = "STATUS_CODE_OK" if success else "STATUS_CODE_ERROR"
    status_message = termination_reason if not success else ""

    return {
        "traceId": trace_id,
        "spanId": root_span_id,
        "name": f"episode/{result.get('task_ref', 'unknown')}",
        "kind": 1,
        "startTimeUnixNano": str(start_nano),
        "endTimeUnixNano": str(end_nano),
        "attributes": attributes,
        "status": {"code": status_code, "message": status_message},
    }


def run_to_otlp(result: dict) -> dict:
    """Convert a TraceCore run artifact to an OTLP ResourceSpans payload dict.

    Parameters
    ----------
    result:
        Run artifact dict as returned by :func:`agent_bench.runner.runner.run`.

    Returns
    -------
    dict
        An OTLP-compatible ``{"resourceSpans": [...]}`` dict suitable for
        ``json.dumps`` and submission to any OTLP/JSON endpoint.
    """
    run_id = result.get("run_id", "")
    trace_id = _run_id_to_trace_id(run_id)
    root_span_id = _root_span_id(run_id)

    action_trace = result.get("action_trace") or []
    step_spans = [
        _step_span(entry, run_id, trace_id, root_span_id)
        for entry in action_trace
    ]

    root = _root_span(result, trace_id, root_span_id, step_spans)
    all_spans = [root] + step_spans

    resource_attrs = [
        _make_attribute("service.name", "tracecore"),
        _make_attribute("service.version", result.get("harness_version", "")),
        _make_attribute("tracecore.task_ref", result.get("task_ref", "")),
    ]

    return {
        "resourceSpans": [
            {
                "resource": {"attributes": resource_attrs},
                "scopeSpans": [
                    {
                        "scope": {"name": _INSTRUMENTATION_SCOPE},
                        "spans": all_spans,
                        "schemaUrl": _SCHEMA_URL,
                    }
                ],
            }
        ]
    }


def export_otlp_json(result: dict, *, indent: int | None = None) -> str:
    """Serialize a run artifact to an OTLP JSON string."""
    return json.dumps(run_to_otlp(result), ensure_ascii=False, indent=indent)
