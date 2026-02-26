"""Reference agent for the sandboxed_code_auditor task."""

from __future__ import annotations


class SandboxedCodeAuditorAgent:
    """Deterministic agent that audits a sandbox runtime and emits ISSUE_ID|AUDIT_CODE."""

    def __init__(self) -> None:
        self.reset({})

    def reset(self, task_spec):
        self.task_spec = task_spec or {}
        self.obs = None
        self.target_key: str | None = None
        self.issue_id: str | None = None
        self.audit_code: str | None = None
        self.read_files: set[str] = set()
        self.pending_extract: str | None = None
        self.submitted: bool = False

    def observe(self, observation):
        self.obs = observation

    def _last_action(self) -> dict:
        return (self.obs or {}).get("last_action") or {}

    def _last_result(self) -> dict:
        return (self.obs or {}).get("last_action_result") or {}

    def act(self):
        last_action = self._last_action()
        last_result = self._last_result()
        action_type = last_action.get("type")

        if action_type == "set_output" and last_result.get("ok"):
            self.submitted = True
            return {"type": "wait", "args": {}}

        if self.submitted:
            return {"type": "wait", "args": {}}

        if action_type == "read_file" and last_result.get("ok"):
            path = last_action.get("args", {}).get("path", "")
            content = last_result.get("content", "")
            self.read_files.add(path)

            if path == "/app/audit_scope.md":
                for line in content.splitlines():
                    if line.startswith("TARGET_KEY="):
                        self.target_key = line.split("=", 1)[1].strip()

            elif path == "/app/src/runtime_guard.py":
                self.pending_extract = "ISSUE_ID"
                return {
                    "type": "extract_value",
                    "args": {"content": content, "key": "ISSUE_ID"},
                }

            elif path == "/app/reports/audit.log":
                self.pending_extract = "AUDIT_CODE"
                return {
                    "type": "extract_value",
                    "args": {"content": content, "key": "AUDIT_CODE"},
                }

        if action_type == "extract_value" and last_result.get("ok"):
            value = last_result.get("value")
            if self.pending_extract == "ISSUE_ID":
                self.issue_id = value
                self.pending_extract = None
            elif self.pending_extract == "AUDIT_CODE":
                self.audit_code = value
                self.pending_extract = None

        if "/app/audit_scope.md" not in self.read_files:
            return {"type": "read_file", "args": {"path": "/app/audit_scope.md"}}

        if "/app/src/runtime_guard.py" not in self.read_files:
            return {"type": "read_file", "args": {"path": "/app/src/runtime_guard.py"}}

        if "/app/reports/audit.log" not in self.read_files:
            return {"type": "read_file", "args": {"path": "/app/reports/audit.log"}}

        if self.issue_id and self.audit_code and self.target_key:
            token = f"{self.issue_id}|{self.audit_code}"
            return {"type": "set_output", "args": {"key": self.target_key, "value": token}}

        return {"type": "wait", "args": {}}
