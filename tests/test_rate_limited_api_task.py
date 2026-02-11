"""Scenario tests for the rate_limited_api task."""

from openclaw_bench.env.environment import Environment

from tasks.rate_limited_api import actions, setup, validate
from tasks.rate_limited_api.shared import OUTPUT_KEY


def _init_env(seed: int = 123) -> Environment:
    env = Environment()
    setup.setup(seed, env)
    actions.set_env(env)
    return env


def test_rate_limited_flow_requires_wait_then_succeeds():
    env = _init_env()
    required_payload = actions.get_client_config()["payload_template"]

    first = actions.call_api("/token", required_payload)
    assert first["ok"] is False
    assert first["error"] == "rate_limited"
    assert first.get("retry_after") == 2

    wait_result = actions.wait(steps=2)
    assert wait_result["ok"] is True

    second = actions.call_api("/token", required_payload)
    assert second["ok"] is False
    assert second["error"] == "temporary_failure"

    third = actions.call_api("/token", required_payload)
    assert third["ok"] is True
    token = third["data"]["token"]

    set_result = actions.set_output(OUTPUT_KEY, token)
    assert set_result["ok"] is True

    validation = validate.validate(env)
    assert validation["ok"] is True


def test_bad_payload_and_wrong_output_key_are_rejected():
    env = _init_env()

    bad_payload_result = actions.call_api("/token", "not json")
    assert bad_payload_result["ok"] is False
    assert bad_payload_result["error"] == "bad_request"

    invalid_output = actions.set_output("WRONG", "value")
    assert invalid_output["ok"] is False
    assert invalid_output["error"] == "invalid_output_key"
