"""Scenario tests for the saas_access_review task."""

from __future__ import annotations

from agent_bench.env.environment import Environment

from tasks.saas_access_review import actions, setup, validate
from tasks.saas_access_review.shared import OUTPUT_KEY, SERVICE_KEY


def _init_env(seed: int = 123) -> Environment:
    env = Environment()
    setup.setup(seed, env)
    actions.set_env(env)
    return env


def test_access_review_flow_requires_wait_and_retry():
    env = _init_env()
    service = env.get_hidden_state(SERVICE_KEY)
    assert service is not None

    readme = actions.read_instructions()
    assert readme["ok"] is True

    request = actions.get_request_details()
    assert request["ok"] is True
    details = request["request"]

    submit = actions.submit_ticket(
        details["request_id"],
        details["user_email"],
        details["target_role"],
        f"Need elevated access for {details['justification_hint']} close tasks.",
    )
    assert submit["ok"] is True

    first = actions.review_status()
    assert first["ok"] is False
    assert first["error"] == "review_pending"
    assert first["retry_after"] >= 1

    actions.wait(first["retry_after"])

    second = actions.review_status()
    assert second["ok"] is False
    assert second["error"] == "temporary_failure"

    third = actions.review_status()
    assert third["ok"] is True
    assert third["recommended_action"] == "approve_role_change"

    confirm = actions.confirm_approval(details["request_id"], third["approval_code"])
    assert confirm["ok"] is True
    token = confirm["token"]

    set_result = actions.set_output(OUTPUT_KEY, token)
    assert set_result["ok"] is True
    validation = validate.validate(env)
    assert validation["ok"] is True


def test_access_review_rejects_bad_justification():
    env = _init_env()

    request = actions.get_request_details()["request"]
    submit = actions.submit_ticket(
        request["request_id"],
        request["user_email"],
        request["target_role"],
        "Need access soon.",
    )
    assert submit["ok"] is False
    assert submit["error"] == "insufficient_justification"
