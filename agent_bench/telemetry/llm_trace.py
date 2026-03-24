from __future__ import annotations

import os
from datetime import datetime, timezone as tz
from typing import Any

from pydantic import BaseModel, Field


REDACTION_TOKEN = "[redacted]"


def llm_trace_redaction_mode() -> str:
    value = os.getenv("TRACECORE_LLM_TRACE_REDACTION", "off")
    normalized = value.strip().lower()
    if normalized in {"full", "all", "on", "true", "1"}:
        return "full"
    if normalized in {"partial", "metadata_only", "meta"}:
        return "partial"
    return "off"


def llm_trace_redaction_enabled() -> bool:
    return llm_trace_redaction_mode() != "off"


def redact_text(value: str | None, *, mode: str | None = None) -> str | None:
    if value is None:
        return None
    active_mode = mode or llm_trace_redaction_mode()
    if active_mode == "off":
        return value
    if active_mode == "partial":
        return f"{REDACTION_TOKEN}:{len(value)}"
    return REDACTION_TOKEN


class LLMCallRequest(BaseModel):
    provider: str
    model: str
    prompt: str = Field(..., description="Rendered prompt text")
    shim_used: bool = False
    metadata: dict[str, Any] | None = None


class LLMCallResponse(BaseModel):
    provider: str
    model: str
    shim_used: bool = False
    completion: str | None = None
    success: bool = True
    error: str | None = None
    calls_used: int | None = None
    tokens_used: int | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz.utc))


class LLMCallTelemetry(BaseModel):
    request: LLMCallRequest
    response: LLMCallResponse

    def as_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        mode = llm_trace_redaction_mode()
        payload["request"]["prompt"] = redact_text(payload["request"].get("prompt"), mode=mode)
        payload["response"]["completion"] = redact_text(payload["response"].get("completion"), mode=mode)
        payload["redaction"] = {
            "enabled": mode != "off",
            "mode": mode,
        }
        return payload


__all__ = [
    "LLMCallTelemetry",
    "LLMCallRequest",
    "LLMCallResponse",
    "llm_trace_redaction_enabled",
    "llm_trace_redaction_mode",
    "redact_text",
]
