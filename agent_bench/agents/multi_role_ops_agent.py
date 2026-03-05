"""Sample multi-agent orchestrated agent for TraceCore tasks."""

from __future__ import annotations

from typing import Any

from agent_bench.agents.multi_agent_orchestrator import (
    MultiAgentOrchestrator,
    OrchestrationPlan,
    RoleContract,
    RosterEntry,
)


class _ReconAgent:
    """Scans README + directory structure to prime shared context."""

    def __init__(self, board: dict[str, Any]):
        self._board = board
        self._observation: dict | None = None

    def reset(self, _task_spec: dict | None) -> None:
        self._observation = None

    def observe(self, observation: dict | None) -> None:
        self._observation = observation
        if not observation:
            return
        last_action = observation.get("last_action") or {}
        last_result = observation.get("last_action_result") or {}
        if not last_result.get("ok"):
            return

        if last_action.get("type") == "read_file" and last_action.get("args", {}).get("path") == "/app/README.md":
            content = last_result.get("content", "")
            for line in content.splitlines():
                if line.startswith("TARGET_KEY="):
                    self._board["target_key"] = line.split("=", 1)[1].strip()
                    break
            signal_paths: list[str] = []
            for line in content.splitlines():
                if line.strip().startswith("- /"):
                    candidate = line.split("-", 1)[1].strip()
                    if candidate:
                        signal_paths.append(candidate)
            prioritized = None
            for path in signal_paths:
                lowered = path.lower()
                if "incident" in lowered or lowered.endswith("manager_ack.txt"):
                    prioritized = path
                    break
            if not prioritized and signal_paths:
                prioritized = signal_paths[0]
            if prioritized:
                self._board["target_path"] = prioritized
            self._board["readme_scanned"] = True
        elif last_action.get("type") == "list_dir":
            files = last_result.get("files", [])
            for entry in files:
                lowered = entry.lower()
                if lowered.endswith(".log") or lowered.endswith(".txt") or "incident" in lowered:
                    self._board.setdefault("target_path", entry)
                    break
            else:
                if files:
                    self._board.setdefault("target_path", files[0])

    def act(self) -> dict:
        if not self._board.get("readme_scanned"):
            return {"type": "read_file", "args": {"path": "/app/README.md"}}
        if not self._board.get("target_path"):
            return {"type": "list_dir", "args": {"path": "/app"}}
        return {"type": "wait", "args": {}}


class _ExecutorAgent:
    """Consumes shared context and produces the final action."""

    def __init__(self, board: dict[str, Any]):
        self._board = board
        self._observation: dict | None = None

    def reset(self, _task_spec: dict | None) -> None:
        self._observation = None
        self._board.pop("payload_read", None)
        self._board.pop("token_value", None)

    def observe(self, observation: dict | None) -> None:
        self._observation = observation
        if not observation:
            return
        last_action = observation.get("last_action") or {}
        last_result = observation.get("last_action_result") or {}
        if not last_result.get("ok"):
            return

        target_path = self._board.get("target_path")
        target_key = self._board.get("target_key")
        if (
            target_path
            and target_key
            and last_action.get("type") == "read_file"
            and last_action.get("args", {}).get("path") == target_path
        ):
            content = last_result.get("content", "")
            token = None
            for line in content.splitlines():
                if f"{target_key}=" in line:
                    token = line.split("=", 1)[1].strip()
                    break
            if token:
                self._board["token_value"] = token

    def act(self) -> dict:
        target_key = self._board.get("target_key")
        target_path = self._board.get("target_path")
        if not target_key or not target_path:
            return {"type": "wait", "args": {}}
        if not self._board.get("payload_read"):
            self._board["payload_read"] = True
            return {"type": "read_file", "args": {"path": target_path}}
        token = self._board.get("token_value")
        if token:
            return {"type": "set_output", "args": {"key": target_key, "value": token}}
        return {"type": "wait", "args": {}}


class MultiRoleOpsAgent:
    """Public TraceCore agent that delegates to the orchestrator."""

    def __init__(self):
        self._board: dict[str, Any] = {}
        self._plan = OrchestrationPlan(
            roster=[
                RosterEntry(
                    contract=RoleContract(
                        name="Recon",
                        description="Scans metadata + filesystem for escalation context",
                        responsibilities=[
                            "Read scenario README",
                            "Identify target key",
                            "Propose candidate artifact path",
                        ],
                        allowed_actions={"read_file", "list_dir", "wait"},
                    ),
                    agent_factory=lambda: _ReconAgent(self._board),
                ),
                RosterEntry(
                    contract=RoleContract(
                        name="Executor",
                        description="Extracts final token and emits output",
                        responsibilities=[
                            "Read validated artifact",
                            "Emit deterministic output",
                        ],
                        allowed_actions={"read_file", "set_output", "wait"},
                    ),
                    agent_factory=lambda: _ExecutorAgent(self._board),
                ),
            ],
            initial_role="Recon",
            handoff_policy=self._handoff_policy,
        )
        self._orchestrator = MultiAgentOrchestrator(self._plan)

    def _handoff_policy(self, roster, last_index, _observation):
        if last_index is None:
            return "Recon"
        role_name = roster[last_index].contract.name
        if role_name == "Recon":
            if self._board.get("target_key") and self._board.get("target_path"):
                return "Executor"
            return "Recon"
        return "Executor"

    def reset(self, task_spec: dict | None) -> None:
        self._board.clear()
        self._orchestrator.reset(task_spec)

    def observe(self, observation: dict | None) -> None:
        self._orchestrator.observe(observation)

    def act(self) -> dict:
        return self._orchestrator.act()


Agent = MultiRoleOpsAgent
