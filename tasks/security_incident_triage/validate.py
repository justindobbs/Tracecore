"""Validator for the security_incident_triage task."""

from __future__ import annotations

TARGET_KEY = "BREACH_TOKEN"
EXPECTED_KEY = "expected_breach_token"


def validate(env) -> dict:
    expected = env.get_hidden_state(EXPECTED_KEY)
    provided = env.get_agent_output(TARGET_KEY)
    if not expected or provided != expected:
        return {"ok": False, "message": "incorrect or missing BREACH_TOKEN"}
    return {"ok": True, "message": "BREACH_TOKEN triaged successfully"}
