"""Validator for the customer_support_escalation task."""

from __future__ import annotations

TARGET_KEY = "ESCALATION_CODE"
EXPECTED_KEY = "expected_escalation_code"


def validate(env) -> dict:
    expected = env.get_hidden_state(EXPECTED_KEY)
    provided = env.get_agent_output(TARGET_KEY)
    if not expected or provided != expected:
        return {"ok": False, "message": "incorrect or missing ESCALATION_CODE"}
    return {"ok": True, "message": "ESCALATION_CODE acknowledged"}
