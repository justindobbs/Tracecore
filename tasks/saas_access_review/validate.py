"""Validator for the saas_access_review task."""

from __future__ import annotations

from tasks.saas_access_review.shared import APPROVAL_KEY, OUTPUT_KEY, REQUEST_KEY, SERVICE_KEY


def validate(env) -> dict:
    expected_code = env.get_hidden_state(APPROVAL_KEY)
    request = env.get_hidden_state(REQUEST_KEY) or {}
    request_id = request.get("request_id")
    provided = env.get_agent_output(OUTPUT_KEY)
    expected = f"{request_id}|{expected_code}"
    if not request_id or not expected_code or provided != expected:
        return {"ok": False, "message": "incorrect or missing ACCESS_REVIEW_TOKEN"}

    service = env.get_hidden_state(SERVICE_KEY)
    if service is None or not getattr(service, "approval_confirmed", False):
        return {"ok": False, "message": "approval was not confirmed through the SaaS workflow"}

    return {"ok": True, "message": "ACCESS_REVIEW_TOKEN confirmed through SaaS workflow"}
