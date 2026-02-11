"""Actions for the rate_limited_api task."""

from __future__ import annotations

import json
from typing import Any

from tasks.rate_limited_api.service import MockRateLimitedAPI
from tasks.rate_limited_api.shared import OUTPUT_KEY, PAYLOAD_KEY, SERVICE_KEY

_ENV = None


def set_env(env) -> None:
    global _ENV
    _ENV = env


def _require_env():
    if _ENV is None:
        raise RuntimeError("Environment not initialized. Did you call set_env()?")
    return _ENV


def _get_service() -> MockRateLimitedAPI:
    env = _require_env()
    service = env.get_hidden_state(SERVICE_KEY)
    if service is None:
        raise RuntimeError("MockRateLimitedAPI missing from hidden state")
    return service


def _coerce_payload(payload: Any) -> dict | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return data
    return None


def call_api(endpoint: str, payload: Any | None = None) -> dict:
    service = _get_service()
    parsed_payload = _coerce_payload(payload)
    if payload is not None and parsed_payload is None:
        return {
            "ok": False,
            "error": "bad_request",
            "message": "payload must be a JSON object",
        }
    return service.call(endpoint, parsed_payload)


def get_client_config() -> dict:
    env = _require_env()
    required = env.get_hidden_state(PAYLOAD_KEY)
    return {"ok": True, "payload_template": dict(required)}


def wait(steps: int = 1) -> dict:
    if not isinstance(steps, int):
        return {"ok": False, "error": "invalid_args", "message": "steps must be int"}
    if steps <= 0:
        return {"ok": False, "error": "invalid_args", "message": "steps must be > 0"}
    service = _get_service()
    service.advance(steps)
    return {"ok": True, "message": f"advanced virtual time by {steps} steps"}


def inspect_status() -> dict:
    service = _get_service()
    status = service.status()
    status.pop("required_payload", None)
    return {"ok": True, "status": status}


def set_output(key: str, value: str) -> dict:
    env = _require_env()
    if key != OUTPUT_KEY:
        return {
            "ok": False,
            "error": "invalid_output_key",
            "message": f"Only {OUTPUT_KEY} may be set in this task.",
        }
    env.set_agent_output(key, value)
    return {"ok": True}
