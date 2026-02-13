import pytest

from agents.naive_llm_agent import NaiveLLMLoopAgent


@pytest.fixture
def agent():
    a = NaiveLLMLoopAgent()
    a.reset({"id": "filesystem_hidden_config", "description": "", "budgets": {}, "actions": {}})
    return a


def make_obs(step, last_action=None, last_result=None, files_seen=None):
    return {
        "step": step,
        "task": {"id": "filesystem_hidden_config", "description": ""},
        "last_action": last_action,
        "last_action_result": last_result,
        "visible_state": {"files_seen": files_seen or []},
        "budget_remaining": {"steps": 100, "tool_calls": 100},
    }


def test_naive_llm_happy_path(agent):
    # Step 1: list root
    agent.observe(make_obs(1))
    action = agent.act()
    assert action == {"type": "list_dir", "args": {"path": "/app"}}

    # Step 2: read first file
    last_result = {"ok": True, "files": ["/app/README.md"]}
    agent.observe(make_obs(2, last_action=action, last_result=last_result, files_seen=["/app/README.md"]))
    action = agent.act()
    assert action == {"type": "read_file", "args": {"path": "/app/README.md"}}

    # Step 3: extract value
    last_result = {"ok": True, "content": "API_KEY=secret"}
    agent.observe(make_obs(3, last_action=action, last_result=last_result, files_seen=["/app/README.md"]))
    action = agent.act()
    assert action == {"type": "extract_value", "args": {"content": "API_KEY=secret", "key": "API_KEY"}}

    # Step 4: set output
    last_result = {"ok": True, "value": "secret"}
    agent.observe(make_obs(4, last_action=action, last_result=last_result, files_seen=["/app/README.md"]))
    action = agent.act()
    assert action == {"type": "set_output", "args": {"key": "API_KEY", "value": "secret"}}

    # Step 5: waits after commit
    last_result = {"ok": True}
    agent.observe(make_obs(5, last_action=action, last_result=last_result, files_seen=["/app/README.md"]))
    action = agent.act()
    assert action == {"type": "wait", "args": {}}


def test_naive_llm_retries_once(agent):
    # Start by listing
    agent.observe(make_obs(1))
    list_action = agent.act()
    assert list_action["type"] == "list_dir"

    # Suppose read_file fails once; agent should retry the same action once
    read_action = {"type": "read_file", "args": {"path": "/app/file.txt"}}
    last_result = {"ok": False, "error": "file_not_found"}
    agent.observe(make_obs(2, last_action=read_action, last_result=last_result))
    retry_action = agent.act()
    assert retry_action == read_action

    # Second failure consumes retry budget; next call should fall back to listing again
    agent.observe(make_obs(3, last_action=read_action, last_result=last_result))
    fallback_action = agent.act()
    assert fallback_action == {"type": "list_dir", "args": {"path": "/app"}}
