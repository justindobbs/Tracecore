"""Reference agent for operations triage tasks."""

from __future__ import annotations


class OpsTriageAgent:
    def __init__(self) -> None:
        self.reset({})

    def reset(self, task_spec):
        self.task_spec = task_spec or {}
        self.obs = None
        self.target_key: str | None = None
        self.files: list[str] = []
        self.seen_paths: set[str] = set()
        self.pending_extract_key: str | None = None
        self.desired_config: dict[str, str] | None = None
        self.live_config: dict[str, str] | None = None

    def observe(self, observation):
        self.obs = observation

    def _parse_config(self, content: str) -> dict[str, str]:
        data: dict[str, str] = {}
        for line in content.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
        return data

    def _record_readme(self, content: str) -> None:
        for line in content.splitlines():
            if line.startswith("TARGET_KEY="):
                self.target_key = line.split("=", 1)[1].strip()
                break

    def _queue_files(self, files: list[str]) -> None:
        ordered = sorted(files)
        self.files = [path for path in ordered if path not in self.seen_paths]

    def _next_file(self) -> str | None:
        while self.files:
            candidate = self.files.pop(0)
            if candidate not in self.seen_paths:
                self.seen_paths.add(candidate)
                return candidate
        return None

    def _maybe_emit_patch(self):
        if self.target_key != "DRIFT_PATCH":
            return None
        if not self.desired_config or not self.live_config:
            return None
        for key, desired in self.desired_config.items():
            if self.live_config.get(key) != desired:
                patch = f"{key}={desired}"
                return {"type": "set_output", "args": {"key": self.target_key, "value": patch}}
        return None

    def act(self):
        last_action = self.obs.get("last_action") if self.obs else None
        last_result = self.obs.get("last_action_result") if self.obs else None
        action_type = last_action.get("type") if isinstance(last_action, dict) else None

        if action_type == "list_dir" and last_result and last_result.get("ok"):
            self._queue_files(last_result.get("files", []))

        if action_type == "read_file" and last_result and last_result.get("ok"):
            content = last_result.get("content", "")
            path = last_action.get("args", {}).get("path") if last_action else ""
            if path.endswith("README.md"):
                self._record_readme(content)
            elif path.endswith("desired.conf"):
                self.desired_config = self._parse_config(content)
            elif path.endswith("live.conf"):
                self.live_config = self._parse_config(content)
            elif self.target_key in {"ALERT_CODE", "RECOVERY_TOKEN"}:
                self.pending_extract_key = self.target_key
                return {"type": "extract_value", "args": {"content": content, "key": self.target_key}}

        if action_type == "extract_value" and last_result and last_result.get("ok"):
            value = last_result.get("value")
            if value is not None and self.pending_extract_key:
                key = self.pending_extract_key
                self.pending_extract_key = None
                return {"type": "set_output", "args": {"key": key, "value": value}}

        if action_type == "set_output" and last_result and last_result.get("ok"):
            return {"type": "wait", "args": {}}

        patch_action = self._maybe_emit_patch()
        if patch_action:
            return patch_action

        if not self.target_key:
            return {"type": "read_file", "args": {"path": "/app/README.md"}}

        if self.target_key == "DRIFT_PATCH":
            if self.desired_config is None:
                return {"type": "read_file", "args": {"path": "/app/desired.conf"}}
            if self.live_config is None:
                return {"type": "read_file", "args": {"path": "/app/live.conf"}}

        if not self.files:
            return {"type": "list_dir", "args": {"path": "/app"}}

        next_path = self._next_file()
        if next_path:
            return {"type": "read_file", "args": {"path": next_path}}

        return {"type": "wait", "args": {}}
