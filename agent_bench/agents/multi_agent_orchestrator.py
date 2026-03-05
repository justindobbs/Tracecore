"""Multi-agent orchestration harness for TraceCore agents.

This module allows composing multiple role-specific agents into a single
TraceCore-compatible orchestrator. Each role is defined by a contract that
captures responsibilities and allowed actions. A roster wires role contracts to
agent factories, while a handoff policy determines which role acts next based on
previous turns and fresh observations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol, Sequence


class AgentProtocol(Protocol):
    """Protocol describing the minimal TraceCore agent surface."""

    def reset(self, task_spec: dict | None) -> None:  # pragma: no cover - protocol
        ...

    def observe(self, observation: dict | None) -> None:  # pragma: no cover - protocol
        ...

    def act(self) -> dict:  # pragma: no cover - protocol
        ...


@dataclass(slots=True)
class RoleContract:
    """Declarative description of a role and its constraints."""

    name: str
    description: str
    responsibilities: list[str]
    allowed_actions: set[str] | None = None
    handoff_on_success: bool = True
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class RosterEntry:
    """Connects a role contract to an agent factory."""

    contract: RoleContract
    agent_factory: Callable[[], AgentProtocol]


HandoffPolicy = Callable[[Sequence[RosterEntry], int | None, dict | None], int | str | None]


@dataclass(slots=True)
class OrchestrationPlan:
    """Plan describing roster, initial role, and handoff strategy."""

    roster: Sequence[RosterEntry]
    initial_role: str | None = None
    handoff_policy: HandoffPolicy | None = None


def round_robin_policy(roster: Sequence[RosterEntry], last_index: int | None, _obs: dict | None) -> int:
    """Cycle through roster entries regardless of observation contents."""

    if not roster:
        raise ValueError("round_robin_policy received empty roster")
    if last_index is None:
        return 0
    return (last_index + 1) % len(roster)


class MultiAgentOrchestrator:
    """Composite agent that routes actions to role-specific subagents."""

    def __init__(self, plan: OrchestrationPlan):
        if not plan.roster:
            raise ValueError("MultiAgentOrchestrator requires at least one roster entry")
        self._plan = plan
        self._roster_instances: list[tuple[RosterEntry, AgentProtocol]] = [
            (entry, entry.agent_factory()) for entry in plan.roster
        ]
        self._handoff_policy = plan.handoff_policy or round_robin_policy
        self._active_index: int = self._resolve_initial_index(plan.initial_role)
        self._last_role_index: int | None = None
        self._last_observation: dict | None = None

    def _resolve_initial_index(self, role_name: str | None) -> int:
        if role_name is None:
            return 0
        for idx, (entry, _) in enumerate(self._roster_instances):
            if entry.contract.name == role_name:
                return idx
        raise ValueError(f"Unknown initial role {role_name!r}")

    def _resolve_index(self, token: int | str) -> int:
        if isinstance(token, int):
            if token < 0 or token >= len(self._roster_instances):
                raise IndexError(f"Role index {token} out of range")
            return token
        for idx, (entry, _) in enumerate(self._roster_instances):
            if entry.contract.name == token:
                return idx
        raise ValueError(f"Unknown role name {token!r}")

    @property
    def current_role(self) -> RoleContract:
        return self._roster_instances[self._active_index][0].contract

    @property
    def roster(self) -> Sequence[RoleContract]:
        return [entry.contract for entry, _ in self._roster_instances]

    def reset(self, task_spec: dict | None) -> None:
        for _, agent in self._roster_instances:
            agent.reset(task_spec)
        self._last_role_index = None
        self._active_index = self._resolve_initial_index(self._plan.initial_role)

    def observe(self, observation: dict | None) -> None:
        self._last_observation = observation
        for _, agent in self._roster_instances:
            agent.observe(observation)
        # Only evaluate handoff after the first act has occurred.
        if self._last_role_index is None:
            return
        next_token = self._handoff_policy(self._plan.roster, self._last_role_index, observation)
        if next_token is not None:
            self._active_index = self._resolve_index(next_token)

    def _enforce_contract(self, contract: RoleContract, action: dict) -> None:
        allowed = contract.allowed_actions
        if not allowed:
            return
        action_type = action.get("type")
        if action_type not in allowed:
            raise ValueError(
                f"Role {contract.name} attempted disallowed action {action_type!r}; "
                f"allowed actions: {sorted(allowed)}"
            )

    def act(self) -> dict:
        entry, agent = self._roster_instances[self._active_index]
        action = agent.act()
        if not isinstance(action, dict):
            raise TypeError("Role agent act() must return an action dict")
        self._enforce_contract(entry.contract, action)
        # Annotate action for downstream telemetry consumers.
        action.setdefault("meta", {})
        if isinstance(action["meta"], dict):
            action["meta"].setdefault("role", entry.contract.name)
        self._last_role_index = self._active_index
        return action


__all__ = [
    "AgentProtocol",
    "RoleContract",
    "RosterEntry",
    "OrchestrationPlan",
    "round_robin_policy",
    "MultiAgentOrchestrator",
]
