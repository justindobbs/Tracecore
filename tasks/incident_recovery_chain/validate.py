"""Validator for the incident_recovery_chain task."""

from __future__ import annotations

TARGET_KEY = "RECOVERY_TOKEN"
EXPECTED_KEY = "expected_recovery_token"


def validate(env) -> dict:
    expected = env.get_hidden_state(EXPECTED_KEY)
    provided = env.get_agent_output(TARGET_KEY)
    if not expected or provided != expected:
        return {"ok": False, "message": "incorrect or missing RECOVERY_TOKEN"}
    return {"ok": True, "message": "Incident recovery token confirmed"}
