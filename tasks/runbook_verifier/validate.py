"""Validator for the runbook_verifier task."""

from __future__ import annotations

from tasks.runbook_verifier.shared import EXPECTED_KEY, TARGET_KEY


def validate(env) -> dict:
    expected = env.get_hidden_state(EXPECTED_KEY)
    provided = env.get_agent_output(TARGET_KEY)
    if not expected or not provided:
        return {"ok": False, "message": "RUNBOOK_CHECKSUM missing"}
    if provided != expected:
        return {"ok": False, "message": "RUNBOOK_CHECKSUM does not match expected"}
    return {"ok": True, "message": "Runbook checksum verified"}
