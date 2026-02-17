"""Base class for pydantic-ai agents in TraceCore."""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from agent_bench.integrations.pydantic_ai.schemas import ActionModel, ObservationModel


class PydanticAIAgent:
    """Base class for TraceCore agents using pydantic-ai.
    
    This class handles the translation between TraceCore's reset/observe/act
    interface and pydantic-ai's agent model. Subclasses should configure
    the model, tools, and system prompt.
    
    Example:
        ```python
        from agent_bench.integrations.pydantic_ai import PydanticAIAgent, filesystem_tools
        
        class MyAgent(PydanticAIAgent):
            def __init__(self):
                super().__init__(
                    model="openai:gpt-4o-mini",
                    tools=filesystem_tools,
                    system_prompt="You are a helpful agent..."
                )
        ```
    """

    def __init__(
        self,
        model: str,
        tools: list,
        system_prompt: str,
    ):
        """Initialize the pydantic-ai agent.
        
        Args:
            model: Model string (e.g., "openai:gpt-4o-mini", "anthropic:claude-3-5-sonnet-20241022")
            tools: List of tool functions to register
            system_prompt: System prompt describing the task and available tools
        """
        self.agent = Agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
        )
        self.obs: ObservationModel | None = None
        self.task_spec: dict[str, Any] = {}

    def reset(self, task_spec: dict) -> None:
        """Reset the agent for a new episode.
        
        Args:
            task_spec: Task specification from TraceCore runner
        """
        self.task_spec = task_spec or {}
        self.obs = None

    def observe(self, observation: dict) -> None:
        """Receive an observation from the environment.
        
        Args:
            observation: Observation dict from TraceCore runner
        """
        self.obs = ObservationModel(**observation)

    def act(self) -> dict:
        """Decide on the next action to take.
        
        Returns:
            Action dict compatible with TraceCore runner
        """
        if self.obs is None:
            raise RuntimeError("No observation received. Call observe() first.")

        # Format observation as context for the agent
        context = self._format_observation()

        # Run the pydantic-ai agent synchronously
        result = self.agent.run_sync(context)

        # Extract the action and convert to dict
        action: ActionModel = result.data
        return action.model_dump()

    def _format_observation(self) -> str:
        """Format the current observation as a prompt for the agent.
        
        Returns:
            Formatted observation string
        """
        if self.obs is None:
            return "No observation available."

        parts = [
            f"Step {self.obs.step}",
            f"Task: {self.obs.task.get('description', 'N/A')}",
            f"Budget remaining: {self.obs.budget_remaining['steps']} steps, {self.obs.budget_remaining['tool_calls']} tool calls",
        ]

        if self.obs.last_action:
            parts.append(f"Last action: {self.obs.last_action}")
        if self.obs.last_action_result:
            parts.append(f"Last result: {self.obs.last_action_result}")

        if self.obs.visible_state:
            parts.append(f"Visible state: {self.obs.visible_state}")

        return "\n".join(parts)
