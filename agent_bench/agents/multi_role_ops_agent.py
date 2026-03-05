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
                stripped = line.strip()
                if stripped.startswith("- /"):
                    candidate = stripped.lstrip("- ")
                    if candidate:
                        signal_paths.append(candidate)
            if signal_paths:
                self._board["signal_paths"] = signal_paths
                # Backwards compatibility for single-path scenarios.
                prioritized = None
                for path in signal_paths:
                    lowered = path.lower()
                    if "incident" in lowered or lowered.endswith("manager_ack.txt"):
                        prioritized = path
                        break
                if not prioritized:
                    prioritized = signal_paths[0]
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
        self._board.pop("token_value", None)
        self._board.setdefault("token_values", {})
        self._board.setdefault("visited_paths", set())
        self._board["signal_cursor"] = 0

    def _maybe_store_tokens(self, content: str, target_key: str | None) -> None:
        token_values: dict[str, str] = self._board.setdefault("token_values", {})
        for line in content.splitlines():
            stripped_line = line.strip()
            if target_key:
                marker = f"{target_key}="
                if marker in stripped_line:
                    token_values[target_key] = stripped_line.split(marker, 1)[1].strip()
                    continue
            if "=" not in stripped_line:
                continue
            key, value = stripped_line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue
            if key == "FINAL_FORMAT" or key == "FORMAT":
                self._board["final_format"] = value
                continue
            if key.endswith("_TOKEN") or (target_key and key == target_key):
                token_values[key] = value

    def observe(self, observation: dict | None) -> None:
        self._observation = observation
        if not observation:
            return
        last_action = observation.get("last_action") or {}
        last_result = observation.get("last_action_result") or {}
        if not last_result.get("ok"):
            return

        if last_action.get("type") == "read_file":
            path = last_action.get("args", {}).get("path")
            content = last_result.get("content", "")
            self._board.setdefault("visited_paths", set()).add(path)
            self._maybe_store_tokens(content, self._board.get("target_key"))

    def _next_signal_path(self) -> str | None:
        paths: list[str] = self._board.get("signal_paths") or []
        visited = self._board.setdefault("visited_paths", set())
        cursor = self._board.get("signal_cursor", 0)
        while cursor < len(paths):
            path = paths[cursor]
            self._board["signal_cursor"] = cursor + 1
            if path not in visited:
                return path
            cursor += 1
        target_path = self._board.get("target_path")
        if target_path and target_path not in visited:
            visited.add(target_path)  # ensure we don't loop
            return target_path
        return None

    def _maybe_emit_token(self) -> dict | None:
        target_key = self._board.get("target_key")
        if not target_key:
            return None
        token_values: dict[str, str] = self._board.get("token_values", {})
        final_format = self._board.get("final_format")
        if final_format:
            try:
                final_value = final_format.format(**token_values)
            except KeyError:
                return None
        else:
            final_value = token_values.get(target_key)
        if not final_value:
            return None
        return {"type": "set_output", "args": {"key": target_key, "value": final_value}}

    def act(self) -> dict:
        path = self._next_signal_path()
        if path:
            return {"type": "read_file", "args": {"path": path}}
        token_action = self._maybe_emit_token()
        if token_action:
            return token_action
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
