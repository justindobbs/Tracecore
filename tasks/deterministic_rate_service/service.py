"""Mock deterministic rate-limited service."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MockDeterministicService:
    secret: str
    required_payload: dict[str, str]
    handshake_phrase: str
    blocked_until: int = 2
    transient_once: bool = True
    now: int = 0
    handshake_id: str | None = None
    handshake_confirmed: bool = False
    token_calls: int = 0
    rate_limit_hits: int = 0
    fatal_errors: int = 0
    history: list[dict] = field(default_factory=list)

    def advance(self, steps: int) -> None:
        if steps < 0:
            raise ValueError("steps must be non-negative")
        self.now += steps

    def status(self) -> dict:
        return {
            "now": self.now,
            "handshake_id": self.handshake_id,
            "handshake_confirmed": self.handshake_confirmed,
            "blocked_until": self.blocked_until,
            "token_calls": self.token_calls,
            "rate_limit_hits": self.rate_limit_hits,
        }

    def _payload_is_valid(self, payload: dict | None) -> bool:
        if payload is None:
            return False
        for key, val in self.required_payload.items():
            if payload.get(key) != val:
                return False
        if payload.get("handshake_id") != self.handshake_id:
            return False
        return True

    def _record(self, entry: dict) -> None:
        self.history.append(entry | {"now": self.now})

    def call(self, endpoint: str, payload: dict | None = None) -> dict:
        if endpoint == "/handshake":
            self.handshake_id = f"hs-{self.now}"
            self.handshake_confirmed = False
            result = {"ok": True, "handshake_id": self.handshake_id}
            self._record({"endpoint": endpoint, "result": result})
            return result

        if endpoint == "/handshake_commit":
            if not payload or payload.get("handshake_id") != self.handshake_id:
                self.fatal_errors += 1
                result = {"ok": False, "error": "invalid_handshake"}
                self._record({"endpoint": endpoint, "result": result})
                return result
            expected_phrase = self.handshake_phrase.replace("<handshake_id>", self.handshake_id)
            if payload.get("response") != expected_phrase:
                self.fatal_errors += 1
                result = {"ok": False, "error": "wrong_phrase"}
                self._record({"endpoint": endpoint, "result": result})
                return result
            self.handshake_confirmed = True
            result = {"ok": True, "message": "handshake_confirmed"}
            self._record({"endpoint": endpoint, "result": result})
            return result

        if endpoint == "/token":
            self.token_calls += 1
            if not self.handshake_confirmed:
                result = {"ok": False, "error": "handshake_required"}
                self._record({"endpoint": endpoint, "result": result})
                return result
            if not self._payload_is_valid(payload):
                self.fatal_errors += 1
                result = {"ok": False, "error": "bad_request"}
                self._record({"endpoint": endpoint, "result": result})
                return result
            if self.now < self.blocked_until:
                retry_after = self.blocked_until - self.now
                self.rate_limit_hits += 1
                result = {
                    "ok": False,
                    "error": "rate_limited",
                    "retry_after": retry_after,
                    "message": "Respect retry window",
                }
                self._record({"endpoint": endpoint, "result": result})
                return result
            if self.transient_once:
                self.transient_once = False
                result = {
                    "ok": False,
                    "error": "temporary_failure",
                    "message": "Server hiccup, retry immediately",
                }
                self._record({"endpoint": endpoint, "result": result})
                return result
            result = {"ok": True, "data": {"token": self.secret}}
            self._record({"endpoint": endpoint, "result": result})
            return result

        result = {"ok": False, "error": "not_found"}
        self._record({"endpoint": endpoint, "result": result})
        return result
