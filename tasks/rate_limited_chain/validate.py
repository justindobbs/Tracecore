"""Validation logic for the rate_limited_chain task."""

from __future__ import annotations

from tasks.rate_limited_chain.shared import OUTPUT_KEY, SECRET_KEY, SERVICE_KEY


def validate(env) -> dict:
    secret = env.get_hidden_state(SECRET_KEY)
    service = env.get_hidden_state(SERVICE_KEY)
    agent_secret = env.get_agent_output(OUTPUT_KEY)

    if not service:
        return {"ok": False, "error": "service_missing"}
    if not service.handshake_confirmed:
        return {"ok": False, "error": "handshake_missing", "message": "handshake never confirmed"}
    if not agent_secret:
        return {"ok": False, "error": "missing_output"}
    if agent_secret != secret:
        return {"ok": False, "error": "wrong_secret"}

    return {"ok": True}
