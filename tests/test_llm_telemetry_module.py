from __future__ import annotations

from agent_bench.telemetry.llm_trace import (
    LLMCallRequest,
    LLMCallResponse,
    LLMCallTelemetry,
    llm_trace_redaction_mode,
    redact_text,
)


def test_redact_text_off_returns_original(monkeypatch):
    monkeypatch.delenv("TRACECORE_LLM_TRACE_REDACTION", raising=False)
    assert llm_trace_redaction_mode() == "off"
    assert redact_text("hello") == "hello"


def test_redact_text_full_mode(monkeypatch):
    monkeypatch.setenv("TRACECORE_LLM_TRACE_REDACTION", "full")
    assert llm_trace_redaction_mode() == "full"
    assert redact_text("secret") == "[redacted]"


def test_redact_text_partial_mode(monkeypatch):
    monkeypatch.setenv("TRACECORE_LLM_TRACE_REDACTION", "partial")
    assert llm_trace_redaction_mode() == "partial"
    assert redact_text("secret") == "[redacted]:6"


def test_llm_call_telemetry_as_dict_redacts_prompt_and_completion(monkeypatch):
    monkeypatch.setenv("TRACECORE_LLM_TRACE_REDACTION", "full")
    payload = LLMCallTelemetry(
        request=LLMCallRequest(
            provider="openai",
            model="gpt-4o-mini",
            prompt="top secret prompt",
            shim_used=True,
        ),
        response=LLMCallResponse(
            provider="openai",
            model="gpt-4o-mini",
            completion="classified completion",
            success=True,
            tokens_used=12,
        ),
    ).as_dict()

    assert payload["request"]["prompt"] == "[redacted]"
    assert payload["response"]["completion"] == "[redacted]"
    assert payload["response"]["tokens_used"] == 12
    assert payload["redaction"] == {"enabled": True, "mode": "full"}
