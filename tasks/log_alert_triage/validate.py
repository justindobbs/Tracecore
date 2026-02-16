"""Validator for the log_alert_triage task."""

from __future__ import annotations

TARGET_KEY = "ALERT_CODE"
EXPECTED_KEY = "expected_alert_code"


def validate(env) -> dict:
    expected = env.get_hidden_state(EXPECTED_KEY)
    provided = env.get_agent_output(TARGET_KEY)
    if not expected or provided != expected:
        return {"ok": False, "message": "incorrect or missing ALERT_CODE"}
    return {"ok": True, "message": "ALERT_CODE triaged successfully"}
