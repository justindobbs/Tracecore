"""Actions for the rate_limited_chain task."""

from __future__ import annotations

import json
from typing import Any

from tasks.rate_limited_chain.service import MockChainAPI
from tasks.rate_limited_chain.shared import (
    HANDSHAKE_TEMPLATE_KEY,
    OUTPUT_KEY,
    PAYLOAD_KEY,
    README_PATH,
    SERVICE_KEY,
)

_ENV = None


def set_env(env) -> None:
    global _ENV
    _ENV = env


def _require_env():
    if _ENV is None:
        raise RuntimeError("Environment not initialized. Did you call set_env()?")
    return _ENV


def _get_service() -> MockChainAPI:
    env = _require_env()
    service = env.get_hidden_state(SERVICE_KEY)
    if service is None:
        raise RuntimeError("MockChainAPI missing from hidden state")
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


def _required_payload() -> dict:
    env = _require_env()
    payload = env.get_hidden_state(PAYLOAD_KEY)
    if not payload:
        raise RuntimeError("required payload missing from hidden state")
    return dict(payload)


def call_api(endpoint: str, payload: Any | None = None) -> dict:
    service = _get_service()
    parsed_payload = _coerce_payload(payload)
    if payload is not None and parsed_payload is None:
        return {
            "ok": False,
            "error": "bad_request",
            "message": "payload must be JSON object",
        }
    return service.call(endpoint, parsed_payload)


def get_handshake_template() -> dict:
    env = _require_env()
    template = env.get_hidden_state(HANDSHAKE_TEMPLATE_KEY)
    if template is None:
        return {
            "ok": False,
            "error": "template_missing",
            "message": "handshake template unavailable",
        }
    return {"ok": True, "template": template}


def read_instructions() -> dict:
    env = _require_env()
    try:
        content = env.read_file(README_PATH)
    except KeyError:
        return {"ok": False, "error": "missing_readme"}
    return {"ok": True, "readme": content}


def get_required_payload() -> dict:
    return {"ok": True, "payload_template": _required_payload()}


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
    return {"ok": True, "status": service.status()}


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
