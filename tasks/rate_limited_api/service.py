"""Mock rate-limited API service used by the task."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MockRateLimitedAPI:
    secret: str
    required_payload: dict[str, object]
    now: int = 0
    blocked_until: int = 2
    transient_failure_pending: bool = True
    access_granted: bool = False
    rate_limit_hits: int = 0
    call_attempts: int = 0
    payload_errors: int = 0

    def advance(self, steps: int) -> None:
        if steps < 0:
            raise ValueError("steps must be non-negative")
        self.now += steps

    def _payload_is_valid(self, payload: dict | None) -> bool:
        if payload is None:
            return False
        for key, value in self.required_payload.items():
            if payload.get(key) != value:
                return False
        return True

    def call(self, endpoint: str, payload: dict | None = None) -> dict:
        self.call_attempts += 1
        if endpoint != "/token":
            return {"ok": False, "error": "not_found"}

        if not self._payload_is_valid(payload):
            self.payload_errors += 1
            return {
                "ok": False,
                "error": "bad_request",
                "message": "Payload missing required fields or values.",
            }

        if self.now < self.blocked_until:
            retry_after = self.blocked_until - self.now
            self.rate_limit_hits += 1
            return {
                "ok": False,
                "error": "rate_limited",
                "retry_after": retry_after,
                "message": "Too many requests. Respect Retry-After before retrying.",
            }

        if self.transient_failure_pending:
            self.transient_failure_pending = False
            return {
                "ok": False,
                "error": "temporary_failure",
                "message": "Upstream service hiccup. Safe to retry immediately.",
            }

        self.access_granted = True
        return {"ok": True, "data": {"token": self.secret}}

    def status(self) -> dict:
        return {
            "now": self.now,
            "blocked_until": self.blocked_until,
            "token_retrieved": self.access_granted,
            "rate_limit_hits": self.rate_limit_hits,
            "call_attempts": self.call_attempts,
            "payload_errors": self.payload_errors,
            "required_payload": dict(self.required_payload),
        }
