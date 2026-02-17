"""Pre-built tool functions for pydantic-ai agents."""

from __future__ import annotations

from agent_bench.integrations.pydantic_ai.schemas import (
    CallApiAction,
    ExtractValueAction,
    ListDirAction,
    ReadFileAction,
    SetOutputAction,
    WaitAction,
)


def list_dir(path: str) -> ListDirAction:
    """List files in a directory.
    
    Args:
        path: Directory path to list
        
    Returns:
        Action to list directory contents
    """
    return ListDirAction.create(path)


def read_file(path: str) -> ReadFileAction:
    """Read contents of a file.
    
    Args:
        path: File path to read
        
    Returns:
        Action to read file contents
    """
    return ReadFileAction.create(path)


def extract_value(content: str, key: str) -> ExtractValueAction:
    """Extract a key-value pair from content.
    
    Args:
        content: Text content to search
        key: Key to extract (e.g., "API_KEY")
        
    Returns:
        Action to extract value from content
    """
    return ExtractValueAction.create(content, key)


def set_output(key: str, value: str) -> SetOutputAction:
    """Set the final output for the task.
    
    Args:
        key: Output key name
        value: Output value
        
    Returns:
        Action to set task output
    """
    return SetOutputAction.create(key, value)


def wait(steps: int = 1) -> WaitAction:
    """Wait for a number of steps.
    
    Args:
        steps: Number of steps to wait (default: 1)
        
    Returns:
        Action to wait
    """
    return WaitAction.create(steps)


def call_api(endpoint: str, payload: dict | None = None) -> CallApiAction:
    """Call an API endpoint.
    
    Args:
        endpoint: API endpoint path
        payload: Optional request payload
        
    Returns:
        Action to call API
    """
    return CallApiAction.create(endpoint, payload)


# Pre-built tool registries for common task types
filesystem_tools = [list_dir, read_file, extract_value, set_output]
api_tools = [call_api, wait, set_output]
