"""Chain-aware reference agent for rate_limited_chain@1."""

from __future__ import annotations


class ChainAgent:
    def __init__(self) -> None:
        self.reset({})

    def reset(self, task_spec):
        self.task_spec = task_spec
        self.payload_template: dict | None = None
        self.handshake_template: str | None = None
        self.handshake_id: str | None = None
        self.handshake_confirmed: bool = False
        self.pending_wait: int = 0
        self.cached_token: str | None = None
        self.output_committed = False
        self.obs = None

    def observe(self, observation):
        self.obs = observation

    def _last(self):
        if not self.obs:
            return None, None, None
        action = self.obs.get("last_action")
        result = self.obs.get("last_action_result")
        action_type = action.get("type") if isinstance(action, dict) else None
        return action, result, action_type

    def _call(self, endpoint: str, payload: dict | None = None) -> dict:
        return {"type": "call_api", "args": {"endpoint": endpoint, "payload": payload}}

    def _handshake_phrase(self) -> str:
        if not self.handshake_template or not self.handshake_id:
            return ""
        filled = self.handshake_template.replace("<handshake_id>", self.handshake_id)

        marker = "respond with:"
        lower_filled = filled.lower()
        start_index = lower_filled.find(marker)
        if start_index != -1:
            phrase = filled[start_index + len(marker) :]
        else:
            phrase = filled

        for separator in ("\n", "\r"):
            sep_index = phrase.find(separator)
            if sep_index != -1:
                phrase = phrase[:sep_index]
                break

        return phrase.strip().strip(". ")

    def _call_token(self) -> dict:
        if self.payload_template is None:
            return {"type": "get_required_payload", "args": {}}
        payload = dict(self.payload_template)
        if self.handshake_id:
            payload["handshake_id"] = self.handshake_id
        return self._call("/token", payload)

    def _commit_output(self, token: str) -> dict:
        self.cached_token = token
        return {"type": "set_output", "args": {"key": "ACCESS_TOKEN", "value": token}}

    def act(self):
        action, last_result, action_type = self._last()

        if action_type == "get_required_payload" and last_result and last_result.get("ok"):
            self.payload_template = dict(last_result.get("payload_template", {}))

        if action_type == "get_handshake_template" and last_result and last_result.get("ok"):
            self.handshake_template = last_result.get("template")
            # once we have a template, ensure we request a handshake immediately
            if not self.handshake_id:
                return self._call("/handshake")

        if action_type == "call_api" and last_result:
            endpoint = action.get("args", {}).get("endpoint") if action else None
            if endpoint == "/handshake":
                if last_result.get("ok"):
                    self.handshake_id = last_result.get("handshake_id")
                    self.handshake_confirmed = False
                else:
                    self.handshake_id = None
                    self.handshake_confirmed = False
            elif endpoint == "/handshake_commit":
                if last_result.get("ok"):
                    self.handshake_confirmed = True
                else:
                    self.handshake_confirmed = False
                    self.handshake_id = None
            elif endpoint == "/token":
                if last_result.get("ok"):
                    token = last_result.get("data", {}).get("token")
                    if token:
                        return self._commit_output(token)
                else:
                    error = last_result.get("error")
                    if error == "rate_limited":
                        retry_after = int(last_result.get("retry_after", 1)) or 1
                        self.pending_wait = retry_after
                        return {"type": "wait", "args": {"steps": retry_after}}
                    if error == "temporary_failure":
                        return self._call_token()
                    if error in {"handshake_required", "invalid_handshake", "handshake_expired"}:
                        self.handshake_id = None
                        self.handshake_confirmed = False
                        return self._call("/handshake")

        if action_type == "wait" and self.pending_wait > 0:
            self.pending_wait = 0
            return self._call_token()

        if action_type == "set_output" and last_result and last_result.get("ok"):
            self.output_committed = True
            return {"type": "wait", "args": {"steps": 1}}

        if self.payload_template is None:
            return {"type": "get_required_payload", "args": {}}

        if self.handshake_template is None:
            return {"type": "get_handshake_template", "args": {}}

        if self.handshake_id is None:
            return self._call("/handshake")

        if not self.handshake_confirmed:
            phrase = self._handshake_phrase()
            if not phrase:
                return {"type": "get_handshake_template", "args": {}}
            return self._call(
                "/handshake_commit",
                {
                    "handshake_id": self.handshake_id,
                    "response": phrase,
                },
            )

        if self.pending_wait > 0:
            return {"type": "wait", "args": {"steps": self.pending_wait}}

        if self.cached_token and not self.output_committed:
            return self._commit_output(self.cached_token)

        return self._call_token()