"""Reference agent for the rate-limited API task."""

from __future__ import annotations


class RateLimitAgent:
    def __init__(self) -> None:
        self.reset({})

    def reset(self, task_spec):
        self.task_spec = task_spec
        self.payload_template: dict | None = None
        self.pending_wait: int = 0
        self.last_token: str | None = None
        self.output_committed: bool = False
        self.obs = None

    def observe(self, observation):
        self.obs = observation

    def _last_action(self):
        if not self.obs:
            return None, None, None
        action = self.obs.get("last_action")
        result = self.obs.get("last_action_result")
        action_type = action.get("type") if isinstance(action, dict) else None
        return action, result, action_type

    def _call_api(self):
        if not self.payload_template:
            return {"type": "get_client_config", "args": {}}
        return {
            "type": "call_api",
            "args": {"endpoint": "/token", "payload": self.payload_template},
        }

    def act(self):
        last_action, last_result, action_type = self._last_action()

        if action_type == "get_client_config" and last_result and last_result.get("ok"):
            self.payload_template = dict(last_result.get("payload_template", {}))
            return self._call_api()

        if action_type == "call_api" and last_result:
            if last_result.get("ok"):
                token = last_result.get("data", {}).get("token")
                if token:
                    self.last_token = token
                    return {
                        "type": "set_output",
                        "args": {"key": "ACCESS_TOKEN", "value": token},
                    }
            else:
                error = last_result.get("error")
                if error == "rate_limited":
                    retry_after = int(last_result.get("retry_after", 1)) or 1
                    self.pending_wait = retry_after
                    return {"type": "wait", "args": {"steps": self.pending_wait}}
                if error == "temporary_failure":
                    return self._call_api()
                if error == "bad_request":
                    self.payload_template = None
                    return {"type": "get_client_config", "args": {}}

        if action_type == "wait" and self.pending_wait > 0:
            self.pending_wait = 0
            return self._call_api()

        if action_type == "set_output" and last_result and last_result.get("ok"):
            self.output_committed = True
            return {"type": "wait", "args": {"steps": 1}}

        if not self.payload_template:
            return {"type": "get_client_config", "args": {}}

        if self.last_token and not self.output_committed:
            return {
                "type": "set_output",
                "args": {"key": "ACCESS_TOKEN", "value": self.last_token},
            }

        return self._call_api()
