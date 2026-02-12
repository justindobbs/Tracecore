"""Scenario tests for the rate_limited_chain task."""

from __future__ import annotations

from agent_bench.env.environment import Environment

from tasks.rate_limited_chain import actions, setup, validate
from tasks.rate_limited_chain.shared import OUTPUT_KEY, SERVICE_KEY


def _init_env(seed: int = 99) -> Environment:
    env = Environment()
    setup.setup(seed, env)
    actions.set_env(env)
    return env


def test_chain_flow_requires_handshake_and_respects_rate_limit():
    env = _init_env()
    service = env.get_hidden_state(SERVICE_KEY)
    assert service is not None

    readme = actions.read_instructions()
    assert readme["ok"] is True

    handshake = actions.call_api("/handshake")
    assert handshake["ok"] is True
    handshake_id = handshake["handshake_id"]

    template = actions.get_handshake_template()
    assert template["ok"] is True

    response = f"CHAIN-{handshake_id}-{service.chain_code}"
    commit = actions.call_api(
        "/handshake_commit",
        {"handshake_id": handshake_id, "response": response},
    )
    assert commit["ok"] is True

    payload = actions.get_required_payload()["payload_template"]
    payload = dict(payload, handshake_id=handshake_id)

    first = actions.call_api("/token", payload)
    assert first["ok"] is False
    assert first["error"] == "rate_limited"
    assert first["retry_after"] >= 1

    actions.wait(steps=first["retry_after"])

    second = actions.call_api("/token", payload)
    assert second["ok"] is False
    assert second["error"] == "temporary_failure"

    third = actions.call_api("/token", payload)
    assert third["ok"] is True
    token = third["data"]["token"]

    set_result = actions.set_output(OUTPUT_KEY, token)
    assert set_result["ok"] is True
    validation = validate.validate(env)
    assert validation["ok"] is True


def test_handshake_commit_must_match_phrase():
    env = _init_env()
    handshake = actions.call_api("/handshake")
    hid = handshake["handshake_id"]

    bad_commit = actions.call_api(
        "/handshake_commit",
        {"handshake_id": hid, "response": "WRONG"},
    )
    assert bad_commit["ok"] is False
    assert bad_commit["error"] in {"wrong_phrase", "invalid_handshake"}
