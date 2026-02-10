"""Toy reference agent (v0)."""

class ToyAgent:
    def __init__(self):
        self.reset(None)

    def reset(self, task_spec):
        self.task = task_spec
        self.memory = {
            "seen_paths": set(),
            "last_errors": {},
            "pending_retry": None,
        }
        self.obs = None

    def observe(self, observation):
        self.obs = observation

    def act(self):
        if self.obs:
            last_action = self.obs.get("last_action")
            last_result = self.obs.get("last_action_result")
            if last_action and last_result and last_result.get("ok"):
                if last_action.get("type") == "read_file":
                    content = last_result.get("content", "")
                    return {"type": "extract_value", "args": {"content": content, "key": "API_KEY"}}
                if last_action.get("type") == "extract_value":
                    value = last_result.get("value")
                    if value is not None:
                        return {"type": "set_output", "args": {"key": "API_KEY", "value": value}}

        if self.memory["pending_retry"] is not None:
            action = self.memory["pending_retry"]
            self.memory["pending_retry"] = None
            return action

        last_result = None if not self.obs else self.obs.get("last_action_result")
        if last_result and not last_result.get("ok", True):
            err = last_result.get("error", "unknown")
            last_action = self.obs.get("last_action")
            print(f"Agent handling error: {err} for action: {last_action}")
            
            # Track errors for debugging
            self.memory["last_errors"][err] = self.memory["last_errors"].get(err, 0) + 1
            
            if err in ("rate_limited", "temporary_failure"):
                # Retry these errors after waiting
                self.memory["pending_retry"] = last_action
                return {"type": "wait", "args": {}}
            elif err == "file_not_found":
                # Don't retry file not found, just continue with next file
                # Mark this path as seen to avoid retrying
                if last_action and last_action.get("type") == "read_file":
                    path = last_action.get("args", {}).get("path")
                    if path:
                        self.memory["seen_paths"].add(path)
                # Continue with next action
                return self._continue_exploration()
            elif err == "key_not_found":
                # Continue with next file if key not found
                return self._continue_exploration()

        visible = {} if not self.obs else self.obs.get("visible_state", {})
        files = visible.get("files_seen", [])
        if not files:
            return {"type": "list_dir", "args": {"path": "/app"}}
        for path in files:
            if path not in self.memory["seen_paths"]:
                self.memory["seen_paths"].add(path)
                return {"type": "read_file", "args": {"path": path}}

        return {"type": "wait", "args": {}}

    def _continue_exploration(self):
        """Helper method to continue exploring files."""
        visible = {} if not self.obs else self.obs.get("visible_state", {})
        files = visible.get("files_seen", [])
        for path in files:
            if path not in self.memory["seen_paths"]:
                self.memory["seen_paths"].add(path)
                return {"type": "read_file", "args": {"path": path}}
        return {"type": "wait", "args": {}}
