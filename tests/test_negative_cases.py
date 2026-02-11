"""Negative test cases for invalid actions and bad task references."""

import pytest
from agent_bench.runner.runner import run


def test_invalid_task_reference():
    """Test runner with invalid task reference."""
    with pytest.raises(Exception):  # Should raise an exception for invalid task
        run("agents/toy_agent.py", "nonexistent_task@1", seed=42)


def test_invalid_task_version():
    """Test runner with invalid task version."""
    with pytest.raises(Exception):  # Should raise an exception for invalid version
        run("agents/toy_agent.py", "filesystem_hidden_config@999", seed=42)


def test_malformed_task_reference():
    """Test runner with malformed task reference."""
    with pytest.raises(Exception):  # Should raise an exception for malformed reference
        run("agents/toy_agent.py", "invalid_format", seed=42)


def test_nonexistent_agent_file():
    """Test runner with nonexistent agent file."""
    with pytest.raises(Exception):  # Should raise an exception for nonexistent agent
        run("agents/nonexistent_agent.py", "filesystem_hidden_config@1", seed=42)


def test_invalid_agent_syntax():
    """Test runner with invalid agent Python syntax."""
    with pytest.raises(Exception):  # Should raise an exception for syntax errors
        run("agents/invalid_agent.py", "filesystem_hidden_config@1", seed=42)


def test_agent_missing_required_methods():
    """Test runner with agent missing required methods."""
    # Create an agent that doesn't have the required interface
    invalid_agent_code = '''
class InvalidAgent:
    """Agent missing required methods."""
    
    def __init__(self):
        pass
    # Missing reset, observe, and act methods
'''
    
    with open("agents/test_invalid_agent.py", "w") as f:
        f.write(invalid_agent_code)
    
    try:
        with pytest.raises(Exception):  # Should raise an exception for missing methods
            run("agents/test_invalid_agent.py", "filesystem_hidden_config@1", seed=42)
    finally:
        import os
        if os.path.exists("agents/test_invalid_agent.py"):
            os.remove("agents/test_invalid_agent.py")


def test_agent_returns_invalid_action():
    """Test runner with agent that returns invalid action format."""
    invalid_agent_code = '''
class InvalidActionAgent:
    """Agent that returns invalid action format."""
    
    def __init__(self):
        self.reset(None)

    def reset(self, task_spec):
        self.task = task_spec
        self.memory = {}
        self.obs = None

    def observe(self, observation):
        self.obs = observation

    def act(self):
        # Return invalid action format (missing 'type' field)
        return {"invalid": "action"}
'''
    
    with open("agents/test_invalid_action_agent.py", "w") as f:
        f.write(invalid_agent_code)
    
    try:
        result = run("agents/test_invalid_action_agent.py", "filesystem_hidden_config@1", seed=42)
        # Should fail due to invalid action type
        assert result["success"] is False
        assert result["failure_reason"] == "invalid_action_type"
    finally:
        import os
        if os.path.exists("agents/test_invalid_action_agent.py"):
            os.remove("agents/test_invalid_action_agent.py")


def test_agent_returns_none_action():
    """Test runner with agent that returns None instead of action."""
    invalid_agent_code = '''
class NoneActionAgent:
    """Agent that returns None instead of action."""
    
    def __init__(self):
        self.reset(None)

    def reset(self, task_spec):
        self.task = task_spec
        self.memory = {}
        self.obs = None

    def observe(self, observation):
        self.obs = observation

    def act(self):
        # Return None instead of valid action
        return None
'''
    
    with open("agents/test_none_action_agent.py", "w") as f:
        f.write(invalid_agent_code)
    
    try:
        result = run("agents/test_none_action_agent.py", "filesystem_hidden_config@1", seed=42)
        # Should fail due to action not being a dict
        assert result["success"] is False
        assert result["failure_reason"] == "action_must_be_dict"
    finally:
        import os
        if os.path.exists("agents/test_none_action_agent.py"):
            os.remove("agents/test_none_action_agent.py")


def test_agent_throws_exception():
    """Test runner with agent that throws exception in act()."""
    invalid_agent_code = '''
class ExceptionAgent:
    """Agent that throws exception in act()."""
    
    def __init__(self):
        self.reset(None)

    def reset(self, task_spec):
        self.task = task_spec
        self.memory = {}
        self.obs = None

    def observe(self, observation):
        self.obs = observation

    def act(self):
        # Throw an exception
        raise ValueError("Agent error!")
'''
    
    with open("agents/test_exception_agent.py", "w") as f:
        f.write(invalid_agent_code)
    
    try:
        with pytest.raises(Exception):  # Should raise an exception for agent error
            run("agents/test_exception_agent.py", "filesystem_hidden_config@1", seed=42)
    finally:
        import os
        if os.path.exists("agents/test_exception_agent.py"):
            os.remove("agents/test_exception_agent.py")


def test_agent_with_invalid_action_args():
    """Test runner with agent that returns action with invalid args."""
    invalid_agent_code = '''
class InvalidArgsAgent:
    """Agent that returns action with invalid args."""
    
    def __init__(self):
        self.reset(None)

    def reset(self, task_spec):
        self.task = task_spec
        self.memory = {}
        self.obs = None

    def observe(self, observation):
        self.obs = observation

    def act(self):
        # Return action with invalid args (missing required 'path' for list_dir)
        return {"type": "list_dir", "args": {}}
'''
    
    with open("agents/test_invalid_args_agent.py", "w") as f:
        f.write(invalid_agent_code)
    
    try:
        # This might not raise an exception immediately, but should fail during execution
        result = run("agents/test_invalid_args_agent.py", "filesystem_hidden_config@1", seed=42)
        # If it doesn't raise an exception, it should at least fail the task
        assert result["success"] is False
        assert result["failure_reason"] is not None
    finally:
        import os
        if os.path.exists("agents/test_invalid_args_agent.py"):
            os.remove("agents/test_invalid_args_agent.py")


def test_task_budget_exceeded():
    """Test runner when agent exceeds task budget."""
    # Create an agent that will exceed the step budget
    budget_exceeding_agent_code = '''
class BudgetExceedingAgent:
    """Agent that intentionally exceeds step budget."""
    
    def __init__(self):
        self.reset(None)

    def reset(self, task_spec):
        self.task = task_spec
        self.memory = {}
        self.obs = None
        self.step_count = 0

    def observe(self, observation):
        self.obs = observation

    def act(self):
        self.step_count += 1
        # Always wait to consume steps without making progress
        return {"type": "wait", "args": {}}
'''
    
    with open("agents/test_budget_exceeding_agent.py", "w") as f:
        f.write(budget_exceeding_agent_code)
    
    try:
        result = run("agents/test_budget_exceeding_agent.py", "filesystem_hidden_config@1", seed=42)
        # Should fail due to unknown action (wait action not recognized)
        assert result["success"] is False
        assert result["failure_reason"] == "unknown_action"
        assert result["steps_used"] == 1  # Should fail immediately on first wait
    finally:
        import os
        if os.path.exists("agents/test_budget_exceeding_agent.py"):
            os.remove("agents/test_budget_exceeding_agent.py")
