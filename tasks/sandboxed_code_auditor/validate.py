"""Validator for sandboxed_code_auditor."""

from __future__ import annotations

TARGET_KEY = "SANDBOX_AUDIT_TOKEN"
EXPECTED_KEY = "expected_sandbox_audit"


def validate(env) -> dict:
    expected = env.get_hidden_state(EXPECTED_KEY)
    provided = env.get_agent_output(TARGET_KEY)
    if not expected or not provided:
        return {"ok": False, "message": "missing audit output"}
    if provided.strip() != expected:
        return {"ok": False, "message": "incorrect audit token"}
    return {"ok": True, "message": "sandbox audit reported"}
