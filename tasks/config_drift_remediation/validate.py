"""Validator for the config_drift_remediation task."""

from __future__ import annotations

TARGET_KEY = "DRIFT_PATCH"
EXPECTED_KEY = "expected_patch"


def validate(env) -> dict:
    expected = env.get_hidden_state(EXPECTED_KEY)
    provided = env.get_agent_output(TARGET_KEY)
    if not expected or provided != expected:
        return {"ok": False, "message": "incorrect or missing DRIFT_PATCH"}
    return {"ok": True, "message": "Config drift remediation prepared"}
