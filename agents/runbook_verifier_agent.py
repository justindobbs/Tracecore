"""Reference agent for the runbook_verifier task."""

from __future__ import annotations

from typing import Dict, List, Optional

from tasks.runbook_verifier.shared import (
    HANDOFF_PATH,
    README_PATH,
    RUNBOOK_INDEX_PATH,
    SEQUENCE_PATH,
    TIMELINE_PATH,
)


class RunbookState:
    def __init__(self) -> None:
        self.target_key: Optional[str] = None
        self.phase_paths: List[str] = []
        self.phase_codes: Dict[str, str] = {}
        self.ack_id: Optional[str] = None
        self.handoff_token: Optional[str] = None
        self.read_files: set[str] = set()
        self.listed: bool = False


class RunbookVerifierAgent:
    """Deterministic agent that stitches runbook artifacts into a checksum."""

    def __init__(self) -> None:
        self.reset({})

    def reset(self, task_spec):
        self.task_spec = task_spec or {}
        self.obs = None
        self.state = RunbookState()
        self._last_checksum: Optional[str] = None

    def observe(self, observation):
        self.obs = observation

    # --------------------- parsing helpers ---------------------
    def _parse_lines(self, content: str) -> dict[str, str]:
        data: dict[str, str] = {}
        for line in content.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
        return data

    def _handle_read(self, path: str, content: str) -> None:
        self.state.read_files.add(path)
        data = self._parse_lines(content)
        if path == README_PATH:
            target = data.get("TARGET_KEY")
            if target:
                self.state.target_key = target
        elif path == RUNBOOK_INDEX_PATH:
            indexed = []
            for idx in range(1, 10):
                path_key = f"PHASE_{idx}_PATH"
                if path_key not in data:
                    break
                indexed.append(data[path_key])
            if indexed:
                self.state.phase_paths = indexed
        elif path in self.state.phase_paths:
            code = data.get("PHASE_CODE")
            if code:
                self.state.phase_codes[path] = code
        elif path == TIMELINE_PATH:
            self.state.ack_id = data.get("ACK_ID")
        elif path == HANDOFF_PATH:
            self.state.handoff_token = data.get("HANDOFF_TOKEN")
        elif path == SEQUENCE_PATH:
            # sequence.log is informational; nothing to parse beyond marking as read
            pass

    def _last_action_succeeded(self, action_type: str) -> bool:
        if not self.obs:
            return False
        last_action = self.obs.get("last_action") or {}
        last_result = self.obs.get("last_action_result") or {}
        return last_action.get("type") == action_type and last_result.get("ok")

    def _process_last_observation(self) -> None:
        if not self.obs:
            return
        last_action = self.obs.get("last_action") or {}
        last_result = self.obs.get("last_action_result") or {}
        if last_action.get("type") == "read_file" and last_result.get("ok"):
            path = last_action.get("args", {}).get("path")
            content = last_result.get("content", "")
            if isinstance(path, str):
                self._handle_read(path, content)
        if last_action.get("type") == "set_output" and last_result.get("ok"):
            self._last_checksum = last_action.get("args", {}).get("value")

    # --------------------- decision logic ---------------------
    def _need(self, path: str) -> bool:
        return path not in self.state.read_files

    def _all_phase_codes_ready(self) -> bool:
        return (
            bool(self.state.phase_paths)
            and len(self.state.phase_codes) == len(self.state.phase_paths)
        )

    def _checksum_ready(self) -> bool:
        return (
            self.state.target_key
            and self._all_phase_codes_ready()
            and self.state.ack_id
            and self.state.handoff_token
        )

    def _compute_checksum(self) -> str:
        ordered_codes = [self.state.phase_codes[path] for path in self.state.phase_paths]
        ordered_codes.append(self.state.ack_id or "")
        ordered_codes.append(self.state.handoff_token or "")
        return "+".join(ordered_codes)

    def act(self):
        self._process_last_observation()

        # After submitting checksum, just wait.
        if self._last_action_succeeded("set_output"):
            return {"type": "wait", "args": {}}

        # Ensure we know available files once.
        if not self.state.listed:
            self.state.listed = True
            return {"type": "list_dir", "args": {"path": "/app"}}

        if self._need(README_PATH):
            return {"type": "read_file", "args": {"path": README_PATH}}

        if self._need(RUNBOOK_INDEX_PATH):
            return {"type": "read_file", "args": {"path": RUNBOOK_INDEX_PATH}}

        for path in self.state.phase_paths:
            if self._need(path):
                return {"type": "read_file", "args": {"path": path}}

        if self._need(TIMELINE_PATH):
            return {"type": "read_file", "args": {"path": TIMELINE_PATH}}

        if self._need(HANDOFF_PATH):
            return {"type": "read_file", "args": {"path": HANDOFF_PATH}}

        if self._need(SEQUENCE_PATH):
            return {"type": "read_file", "args": {"path": SEQUENCE_PATH}}

        if self._checksum_ready():
            checksum = self._compute_checksum()
            self._last_checksum = checksum
            return {
                "type": "set_output",
                "args": {"key": self.state.target_key, "value": checksum},
            }

        # Default idle to avoid unnecessary retries.
        return {"type": "wait", "args": {}}
