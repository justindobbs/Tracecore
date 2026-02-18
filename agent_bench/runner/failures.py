"""Shared failure taxonomy for run results."""

from __future__ import annotations

FAILURE_TYPES: tuple[str, ...] = (
    "budget_exhausted",
    "invalid_action",
    "sandbox_violation",
    "logic_failure",
    "timeout",
    "non_termination",  # Reserved for future use; never emitted by the current runner.
)

_TERMINATION_TO_FAILURE: dict[str, str] = {
    "timeout": "timeout",
    "steps_exhausted": "budget_exhausted",
    "tool_calls_exhausted": "budget_exhausted",
    "invalid_action": "invalid_action",
    "action_exception": "invalid_action",
    "sandbox_violation": "sandbox_violation",
    "non_termination": "non_termination",
    "logic_failure": "logic_failure",
}


def validate_failure_type(success: bool, failure_type: str | None) -> str | None:
    """Ensure failure types are consistent with the taxonomy."""

    if success:
        return None
    if failure_type not in FAILURE_TYPES:
        raise ValueError(
            f"failure_type must be one of {FAILURE_TYPES} when success=False; got {failure_type!r}"
        )
    return failure_type


def classify_failure(termination_reason: str, fallback: str = "logic_failure") -> str:
    """Map runner termination reasons to the canonical taxonomy."""

    return _TERMINATION_TO_FAILURE.get(termination_reason, fallback)


def ensure_failure_type(payload: dict) -> dict:
    """Guarantee payload has a valid failure_type key.

    Mutates and returns the payload for convenience so callers can chain.
    """

    success = bool(payload.get("success"))
    if success:
        payload["failure_type"] = None
        return payload

    failure_type = payload.get("failure_type")
    if not failure_type:
        failure_type = classify_failure(payload.get("termination_reason") or "")
    payload["failure_type"] = validate_failure_type(False, failure_type)
    return payload
