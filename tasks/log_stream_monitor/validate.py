"""Validator for the log_stream_monitor task."""

from __future__ import annotations

STREAM_CODE_KEY = "STREAM_CODE"
EXPECTED_KEY = "expected_stream_code"


def validate(env) -> dict:
    expected = env.get_hidden_state(EXPECTED_KEY)
    provided = env.get_agent_output(STREAM_CODE_KEY)
    if not expected or provided != expected:
        return {"ok": False, "message": "incorrect or missing STREAM_CODE"}
    return {"ok": True, "message": "STREAM_CODE detected and reported correctly"}
