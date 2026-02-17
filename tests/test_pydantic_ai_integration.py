"""Tests for pydantic-ai integration."""

from __future__ import annotations

import pytest

from agent_bench.integrations.pydantic_ai import (
    ActionModel,
    ExtractValueAction,
    ListDirAction,
    ObservationModel,
    PydanticAIAgent,
    ReadFileAction,
    SetOutputAction,
    filesystem_tools,
)


def test_observation_schema_validation():
    """ObservationModel validates TraceCore observation dicts."""
    obs_dict = {
        "step": 1,
        "task": {"id": "filesystem_hidden_config", "description": "Find API key"},
        "last_action": None,
        "last_action_result": None,
        "visible_state": {"files_seen": ["/app/readme.txt"]},
        "budget_remaining": {"steps": 199, "tool_calls": 40},
    }
    
    obs = ObservationModel(**obs_dict)
    
    assert obs.step == 1
    assert obs.task["id"] == "filesystem_hidden_config"
    assert obs.visible_state["files_seen"] == ["/app/readme.txt"]
    assert obs.budget_remaining["steps"] == 199


def test_action_schema_validation():
    """ActionModel subclasses validate and serialize correctly."""
    # ListDirAction
    list_action = ListDirAction.create("/app")
    assert list_action.type == "list_dir"
    assert list_action.args == {"path": "/app"}
    assert list_action.model_dump() == {"type": "list_dir", "args": {"path": "/app"}}
    
    # ReadFileAction
    read_action = ReadFileAction.create("/app/config.txt")
    assert read_action.type == "read_file"
    assert read_action.args == {"path": "/app/config.txt"}
    
    # ExtractValueAction
    extract_action = ExtractValueAction.create("API_KEY=secret", "API_KEY")
    assert extract_action.type == "extract_value"
    assert extract_action.args == {"content": "API_KEY=secret", "key": "API_KEY"}
    
    # SetOutputAction
    output_action = SetOutputAction.create("API_KEY", "secret")
    assert output_action.type == "set_output"
    assert output_action.args == {"key": "API_KEY", "value": "secret"}


def test_tool_registry():
    """Filesystem tools return valid ActionModels."""
    from agent_bench.integrations.pydantic_ai.tools import (
        extract_value,
        list_dir,
        read_file,
        set_output,
    )
    
    # Test each tool
    list_action = list_dir("/app")
    assert isinstance(list_action, ListDirAction)
    assert list_action.args["path"] == "/app"
    
    read_action = read_file("/app/file.txt")
    assert isinstance(read_action, ReadFileAction)
    
    extract_action = extract_value("content", "KEY")
    assert isinstance(extract_action, ExtractValueAction)
    
    output_action = set_output("KEY", "value")
    assert isinstance(output_action, SetOutputAction)
    
    # Verify filesystem_tools list
    assert len(filesystem_tools) == 4
    assert all(callable(tool) for tool in filesystem_tools)


def test_agent_interface():
    """PydanticAIAgent implements TraceCore agent interface."""
    # Use TestModel to avoid external API calls
    try:
        from pydantic_ai import models
        
        agent = PydanticAIAgent(
            model="test",
            tools=filesystem_tools,
            system_prompt="Test agent",
        )
    except ImportError:
        pytest.skip("pydantic-ai not installed")
    
    # Test reset
    agent.reset({"seed": 42})
    assert agent.task_spec == {"seed": 42}
    assert agent.obs is None
    
    # Test observe
    obs_dict = {
        "step": 1,
        "task": {"id": "test", "description": "Test task"},
        "last_action": None,
        "last_action_result": None,
        "visible_state": {},
        "budget_remaining": {"steps": 100, "tool_calls": 20},
    }
    agent.observe(obs_dict)
    assert agent.obs is not None
    assert agent.obs.step == 1


def test_filesystem_task_mock():
    """Test agent interface without requiring external API calls."""
    try:
        from pydantic_ai import Agent
    except ImportError:
        pytest.skip("pydantic-ai not installed")
    
    # Create agent with test model
    agent = PydanticAIAgent(
        model="test",
        tools=filesystem_tools,
        system_prompt="Find API_KEY in filesystem",
    )
    
    # Reset and observe
    agent.reset({"seed": 42})
    obs_dict = {
        "step": 1,
        "task": {"id": "filesystem_hidden_config", "description": "Find API key"},
        "last_action": None,
        "last_action_result": None,
        "visible_state": {},
        "budget_remaining": {"steps": 200, "tool_calls": 40},
    }
    agent.observe(obs_dict)
    
    # Verify observation was stored
    assert agent.obs is not None
    assert agent.obs.step == 1
    assert agent.obs.task["id"] == "filesystem_hidden_config"
    
    # Note: We can't test act() without a real model or proper mock setup
    # The test model API has changed in pydantic-ai, so we just verify
    # the agent interface works correctly


@pytest.mark.skipif(
    True,
    reason="Requires API key and network access - run manually with OPENAI_API_KEY set",
)
def test_filesystem_task_live():
    """Live test with real LLM (requires API key)."""
    import os
    
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    
    from agents.pydantic_ai_agent import FilesystemPydanticAgent
    
    agent = FilesystemPydanticAgent()
    
    # Simulate a simple interaction
    agent.reset({"seed": 42})
    obs_dict = {
        "step": 1,
        "task": {"id": "filesystem_hidden_config", "description": "Find API key"},
        "last_action": None,
        "last_action_result": None,
        "visible_state": {"files_seen": []},
        "budget_remaining": {"steps": 200, "tool_calls": 40},
    }
    agent.observe(obs_dict)
    
    # Get first action
    action = agent.act()
    
    # Should be a valid action
    assert isinstance(action, dict)
    assert "type" in action
    assert "args" in action
    assert action["type"] in ["list_dir", "read_file", "extract_value", "set_output"]
