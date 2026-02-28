"""Pydantic telemetry models for LLM calls."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LLMCallTelemetry(BaseModel):
    request: LLMCallRequest
    response: LLMCallResponse

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump()


__all__ = ["LLMCallTelemetry", "LLMCallRequest", "LLMCallResponse"]
