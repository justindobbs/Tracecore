"""Mock service for the rate_limited_chain task."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MockChainAPI:
    secret: str
    required_payload: dict[str, str]
    chain_code: str
    now: int = 0
    blocked_until: int = 3
    handshake_window: int = 4
    transient_pending: bool = True
    handshake_id: str | None = None
    handshake_expires_at: int | None = None
    handshake_confirmed: bool = False
    rate_limit_hits: int = 0
    token_calls: int = 0

    def advance(self, steps: int) -> None:
        if steps < 0:
            raise ValueError("steps must be non-negative")
        self.now += steps

    def status(self) -> dict:
        return {
            "now": self.now,
            "blocked_until": self.blocked_until,
            "handshake_id": self.handshake_id,
            "handshake_confirmed": self.handshake_confirmed,
            "rate_limit_hits": self.rate_limit_hits,
            "token_calls": self.token_calls,
        }

    def _payload_is_valid(self, payload: dict | None) -> bool:
        if payload is None:
            return False
        for key, value in self.required_payload.items():
            if payload.get(key) != value:
                return False
        return True

    def _expected_phrase(self) -> str | None:
        if not self.handshake_id:
            return None
        return f"CHAIN-{self.handshake_id}-{self.chain_code}"

    def call(self, endpoint: str, payload: dict | None = None) -> dict:
        if endpoint == "/handshake":
            self.handshake_id = f"hs-{self.now}"
            self.handshake_expires_at = self.now + self.handshake_window
            self.handshake_confirmed = False
            return {
                "ok": True,
                "handshake_id": self.handshake_id,
                "expires_at_step": self.handshake_expires_at,
            }

        if endpoint == "/handshake_commit":
            if not payload:
                return {"ok": False, "error": "invalid_handshake", "message": "payload required"}
            if payload.get("handshake_id") != self.handshake_id:
                return {"ok": False, "error": "invalid_handshake", "message": "unknown handshake_id"}
            if self.handshake_expires_at is not None and self.now > self.handshake_expires_at:
                return {"ok": False, "error": "handshake_expired", "message": "request a new handshake"}
            expected = self._expected_phrase()
            if payload.get("response") != expected:
                return {"ok": False, "error": "wrong_phrase", "message": "response does not match template"}
            self.handshake_confirmed = True
            return {"ok": True, "message": "handshake_confirmed"}

        if endpoint == "/token":
            self.token_calls += 1
            if not self.handshake_confirmed:
                return {"ok": False, "error": "handshake_required", "message": "complete handshake first"}
            if not self._payload_is_valid(payload):
                return {
                    "ok": False,
                    "error": "bad_request",
                    "message": "payload missing required fields or values",
                }
            if payload.get("handshake_id") != self.handshake_id:
                return {"ok": False, "error": "invalid_handshake", "message": "stale handshake"}
            if self.now < self.blocked_until:
                retry_after = self.blocked_until - self.now
                self.rate_limit_hits += 1
                return {
                    "ok": False,
                    "error": "rate_limited",
                    "retry_after": retry_after,
                    "message": "Respect retry window before calling /token again",
                }
            if self.transient_pending:
                self.transient_pending = False
                return {
                    "ok": False,
                    "error": "temporary_failure",
                    "message": "Chain service hiccup. Retry immediately.",
                }
            return {"ok": True, "data": {"token": self.secret}}

        return {"ok": False, "error": "not_found", "message": "unknown endpoint"}
