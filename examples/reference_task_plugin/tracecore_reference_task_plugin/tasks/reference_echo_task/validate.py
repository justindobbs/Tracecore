from __future__ import annotations


def validate(env):
    expected = env.get_hidden_state("expected_token")
    submitted = env.get_agent_output("PLUGIN_TOKEN")
    if submitted == expected:
        return {"ok": True, "message": "plugin token recovered"}
    return {"ok": False, "message": "incorrect or missing plugin token"}
