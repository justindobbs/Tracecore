"""Structured planner-style baseline agent."""

from __future__ import annotations


class StructuredPlannerAgent:
    """Maintains a simple plan queue and retries transient failures."""

    def __init__(self) -> None:
        self.reset({})

    def reset(self, task_spec):
        self.task_spec = task_spec or {}
        self.obs = None
        self.plan: list[dict] = []
        self.payload_template: dict | None = None
        self.handshake_template: str | None = None
        self.handshake_id: str | None = None
        self.pending_wait: int = 0
        self.cached_token: str | None = None
        self.output_committed = False
        self.output_key = self.task_spec.get("output_key", "ACCESS_TOKEN")

    def observe(self, observation):
        self.obs = observation

    def _schedule(self, action: dict) -> None:
        self.plan.append(action)

    def _next(self) -> dict | None:
        if self.plan:
            return self.plan.pop(0)
        return None

    def _ensure_handshake_plan(self):
        if not self.plan:
            self.plan.extend(
                [
                    {"type": "get_handshake_template", "args": {}},
                    {"type": "call_api", "args": {"endpoint": "/handshake"}},
                ]
            )

    def act(self) -> dict:
        last_action = self.obs.get("last_action") if self.obs else None
        last_result = self.obs.get("last_action_result") if self.obs else None
        action_type = last_action.get("type") if last_action else None

        if action_type == "get_required_payload" and last_result and last_result.get("ok"):
            self.payload_template = dict(last_result.get("payload_template", {}))

        if action_type == "get_handshake_template" and last_result and last_result.get("ok"):
            self.handshake_template = last_result.get("template")

        if action_type == "call_api" and last_result:
            endpoint = last_action.get("args", {}).get("endpoint") if last_action else None
            if endpoint == "/handshake":
                if last_result.get("ok"):
                    self.handshake_id = last_result.get("handshake_id")
                    response = self._handshake_phrase()
                    return {
                        "type": "call_api",
                        "args": {
                            "endpoint": "/handshake_commit",
                            "payload": {"handshake_id": self.handshake_id, "response": response},
                        },
                    }
                self.handshake_id = None
            elif endpoint == "/handshake_commit" and not last_result.get("ok"):
                self.handshake_id = None
            elif endpoint == "/token":
                if last_result.get("ok"):
                    token = last_result.get("data", {}).get("token")
                    if token:
                        self.cached_token = token
                        return {"type": "set_output", "args": {"key": self.output_key, "value": token}}
                else:
                    error = last_result.get("error")
                    if error == "rate_limited":
                        retry_after = int(last_result.get("retry_after", 1)) or 1
                        self.pending_wait = retry_after
                        return {"type": "wait", "args": {"steps": retry_after}}
                    if error == "temporary_failure":
                        return self._call_token()
                    if error in {"bad_request", "invalid_handshake", "handshake_expired"}:
                        self.payload_template = None
                        self.handshake_id = None
                        self.plan.clear()
                        self._ensure_handshake_plan()
                        return self._next() or self._call_token()

        if action_type == "set_output" and last_result and last_result.get("ok"):
            self.output_committed = True
            return {"type": "wait", "args": {"steps": 1}}

        if self.pending_wait > 0:
            if action_type == "wait":
                self.pending_wait = 0
            else:
                return {"type": "wait", "args": {"steps": self.pending_wait}}

        if self.cached_token and not self.output_committed:
            return {"type": "set_output", "args": {"key": self.output_key, "value": self.cached_token}}

        next_action = self._next()
        if next_action:
            return next_action

        if self.payload_template is None:
            return {"type": "get_required_payload", "args": {}}

        if self.handshake_id is None:
            self._ensure_handshake_plan()
            return self._next()

        return self._call_token()

    def _call_token(self) -> dict:
        payload = dict(self.payload_template or {})
        if self.handshake_id:
            payload["handshake_id"] = self.handshake_id
        return {"type": "call_api", "args": {"endpoint": "/token", "payload": payload}}

    def _handshake_phrase(self) -> str:
        if not self.handshake_template or not self.handshake_id:
            return ""
        template = self.handshake_template.replace("<handshake_id>", self.handshake_id)
        marker = "respond with:"
        lower = template.lower()
        idx = lower.find(marker)
        phrase = template[idx + len(marker):] if idx != -1 else template
        for sep in ("\n", "\r"):
            pos = phrase.find(sep)
            if pos != -1:
                phrase = phrase[:pos]
                break
        return phrase.strip().strip(". ")
