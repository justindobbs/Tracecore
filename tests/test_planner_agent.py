import pytest

from agents.planner_agent import StructuredPlannerAgent


def make_obs(step, last_action=None, last_result=None):
    return {
        "step": step,
        "task": {"id": "rate_limited_chain", "description": ""},
        "last_action": last_action,
        "last_action_result": last_result,
        "visible_state": {},
        "budget_remaining": {"steps": 100, "tool_calls": 100},
    }


def agent(output_key="ACCESS_TOKEN"):
    a = StructuredPlannerAgent()
    a.reset({"id": "rate_limited_chain", "description": "", "budgets": {}, "actions": {}, "output_key": output_key})
    return a


def test_planner_handshake_happy_path():
    a = agent()

    # 1) Starts by fetching required payload
    a.observe(make_obs(1))
    action = a.act()
    assert action == {"type": "get_required_payload", "args": {}}

    # 2) Cache payload template
    payload_result = {"ok": True, "payload_template": {"foo": "bar"}}
    a.observe(make_obs(2, last_action=action, last_result=payload_result))
    action = a.act()
    assert action == {"type": "get_handshake_template", "args": {}}

    # 3) Cache handshake template
    handshake_tpl = {"ok": True, "template": "<handshake_id>: respond with: pong"}
    a.observe(make_obs(3, last_action=action, last_result=handshake_tpl))
    action = a.act()
    assert action == {"type": "call_api", "args": {"endpoint": "/handshake"}}

    # 4) On successful handshake, commit response
    handshake_result = {"ok": True, "handshake_id": "abc123"}
    a.observe(make_obs(4, last_action=action, last_result=handshake_result))
    action = a.act()
    assert action["type"] == "call_api"
    assert action["args"]["endpoint"] == "/handshake_commit"
    assert action["args"]["payload"]["handshake_id"] == "abc123"

    # 5) After commit success, should request token with merged payload
    commit_result = {"ok": True}
    a.observe(make_obs(5, last_action=action, last_result=commit_result))
    action = a.act()
    assert action == {
        "type": "call_api",
        "args": {"endpoint": "/token", "payload": {"foo": "bar", "handshake_id": "abc123"}},
    }


def test_planner_rate_limit_wait_and_retry():
    a = agent()
    # prime payload template
    a.payload_template = {"foo": "bar"}
    a.handshake_id = "abc123"

    token_action = {"type": "call_api", "args": {"endpoint": "/token", "payload": {"foo": "bar", "handshake_id": "abc123"}}}
    rate_limited = {"ok": False, "error": "rate_limited", "retry_after": 3}
    a.observe(make_obs(1, last_action=token_action, last_result=rate_limited))
    action = a.act()
    assert action == {"type": "wait", "args": {"steps": 3}}

    # After waiting, should replay wait once then retry token
    wait_action = {"type": "wait", "args": {"steps": 3}}
    wait_result = {"ok": True}
    a.observe(make_obs(2, last_action=wait_action, last_result=wait_result))
    action = a.act()
    assert action == token_action


def test_planner_reset_clears_state():
    a = agent(output_key="FOO")
    a.cached_token = "tok"
    a.handshake_id = "old"
    a.pending_wait = 5

    a.reset({"id": "rate_limited_chain", "description": "", "budgets": {}, "actions": {}, "output_key": "BAR"})
    assert a.cached_token is None
    assert a.handshake_id is None
    assert a.pending_wait == 0
    assert a.output_key == "BAR"
    assert a.plan == []
