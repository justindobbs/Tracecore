"""Actions for the saas_access_review task."""

from __future__ import annotations

from tasks.saas_access_review.shared import OUTPUT_KEY, README_PATH, REQUEST_KEY, SERVICE_KEY

_ENV = None


def set_env(env) -> None:
    global _ENV
    _ENV = env


def _require_env():
    if _ENV is None:
        raise RuntimeError("Environment not initialized. Did you call set_env()?")
    return _ENV


def _get_service():
    env = _require_env()
    service = env.get_hidden_state(SERVICE_KEY)
    if service is None:
        raise RuntimeError("MockSaaSAccessService missing from hidden state")
    return service


def read_instructions() -> dict:
    env = _require_env()
    try:
        content = env.read_file(README_PATH)
    except KeyError:
        return {"ok": False, "error": "missing_readme"}
    return {"ok": True, "readme": content}


def get_request_details() -> dict:
    env = _require_env()
    request = env.get_hidden_state(REQUEST_KEY)
    if not request:
        return {"ok": False, "error": "missing_request"}
    return {"ok": True, "request": dict(request)}


def submit_ticket(request_id: str, user_email: str, target_role: str, justification: str) -> dict:
    service = _get_service()
    return service.submit_ticket(
        {
            "request_id": request_id,
            "user_email": user_email,
            "target_role": target_role,
            "justification": justification,
        }
    )


def review_status() -> dict:
    service = _get_service()
    return service.review_status()


def confirm_approval(request_id: str, approval_code: str) -> dict:
    service = _get_service()
    return service.confirm_approval({"request_id": request_id, "approval_code": approval_code})


def wait(steps: int = 1) -> dict:
    if not isinstance(steps, int):
        return {"ok": False, "error": "invalid_args", "message": "steps must be int"}
    if steps <= 0:
        return {"ok": False, "error": "invalid_args", "message": "steps must be > 0"}
    service = _get_service()
    service.advance(steps)
    return {"ok": True, "message": f"advanced review clock by {steps} steps"}


def inspect_status() -> dict:
    service = _get_service()
    return {"ok": True, "status": service.status()}


def set_output(key: str, value: str) -> dict:
    env = _require_env()
    if key != OUTPUT_KEY:
        return {
            "ok": False,
            "error": "invalid_output_key",
            "message": f"Only {OUTPUT_KEY} may be set in this task.",
        }
    env.set_agent_output(key, value)
    return {"ok": True}
