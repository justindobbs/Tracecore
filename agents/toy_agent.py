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
        if self.memory["pending_retry"] is not None:
            action = self.memory["pending_retry"]
            self.memory["pending_retry"] = None
            return action

        last_result = None if not self.obs else self.obs.get("last_action_result")
        if last_result and not last_result.get("ok", True):
            err = last_result.get("error", "unknown")
            last_action = self.obs.get("last_action")
            if err in ("rate_limited", "temporary_failure"):
                self.memory["pending_retry"] = last_action
                return {"type": "wait", "args": {}}

        visible = {} if not self.obs else self.obs.get("visible_state", {})
        files = visible.get("files_seen", [])
        for path in files:
            if path not in self.memory["seen_paths"]:
                self.memory["seen_paths"].add(path)
                return {"type": "read_file", "args": {"path": path}}

        return {"type": "wait", "args": {}}
