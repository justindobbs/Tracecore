"""Pydantic schemas for TraceCore observations and actions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ObservationModel(BaseModel):
    """TraceCore observation provided to agents each step."""

    step: int = Field(description="Current step number in the episode")
    task: dict[str, Any] = Field(description="Task metadata (id, description)")
    last_action: dict[str, Any] | None = Field(
        default=None, description="Previous action taken by the agent"
    )
    last_action_result: dict[str, Any] | None = Field(
        default=None, description="Result of the previous action"
    )
    visible_state: dict[str, Any] = Field(
        description="Task-specific visible state (e.g., files_seen)"
    )
    budget_remaining: dict[str, int] = Field(
        description="Remaining steps and tool_calls budget"
    )


class ListDirAction(BaseModel):
    """List files in a directory."""

    type: Literal["list_dir"] = "list_dir"
    args: dict[str, str] = Field(description="Arguments: {path: str}")

    @classmethod
    def create(cls, path: str) -> ListDirAction:
        return cls(args={"path": path})


class ReadFileAction(BaseModel):
    """Read contents of a file."""

    type: Literal["read_file"] = "read_file"
    args: dict[str, str] = Field(description="Arguments: {path: str}")

    @classmethod
    def create(cls, path: str) -> ReadFileAction:
        return cls(args={"path": path})


class ExtractValueAction(BaseModel):
    """Extract a key-value pair from content."""

    type: Literal["extract_value"] = "extract_value"
    args: dict[str, str] = Field(description="Arguments: {content: str, key: str}")

    @classmethod
    def create(cls, content: str, key: str) -> ExtractValueAction:
        return cls(args={"content": content, "key": key})


class SetOutputAction(BaseModel):
    """Set the final output for the task."""

    type: Literal["set_output"] = "set_output"
    args: dict[str, str] = Field(description="Arguments: {key: str, value: str}")

    @classmethod
    def create(cls, key: str, value: str) -> SetOutputAction:
        return cls(args={"key": key, "value": value})


class WaitAction(BaseModel):
    """Wait for a number of steps (used in rate-limited tasks)."""

    type: Literal["wait"] = "wait"
    args: dict[str, int] = Field(description="Arguments: {steps: int}", default_factory=dict)

    @classmethod
    def create(cls, steps: int = 1) -> WaitAction:
        return cls(args={"steps": steps})


class CallApiAction(BaseModel):
    """Call an API endpoint (used in API tasks)."""

    type: Literal["call_api"] = "call_api"
    args: dict[str, Any] = Field(
        description="Arguments: {endpoint: str, payload: dict | None}"
    )

    @classmethod
    def create(cls, endpoint: str, payload: dict[str, Any] | None = None) -> CallApiAction:
        return cls(args={"endpoint": endpoint, "payload": payload})


ActionModel = (
    ListDirAction
    | ReadFileAction
    | ExtractValueAction
    | SetOutputAction
    | WaitAction
    | CallApiAction
)
