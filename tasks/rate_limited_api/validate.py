"""Validator for the rate_limited_api task."""

from __future__ import annotations

from tasks.rate_limited_api.shared import OUTPUT_KEY, SECRET_KEY, SERVICE_KEY


def validate(env) -> dict:
    expected = env.get_hidden_state(SECRET_KEY)
    provided = env.get_agent_output(OUTPUT_KEY)
    if not expected or provided != expected:
        return {"ok": False, "message": "incorrect or missing ACCESS_TOKEN"}

    service = env.get_hidden_state(SERVICE_KEY)
    if service is None or not getattr(service, "access_granted", False):
        return {
            "ok": False,
            "message": "token not retrieved from API (access_granted flag missing)",
        }

    return {"ok": True, "message": "ACCESS_TOKEN retrieved from rate-limited API"}
