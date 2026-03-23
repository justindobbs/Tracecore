"""Mock SaaS admin service for deterministic access review."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MockSaaSAccessService:
    request_id: str
    user_email: str
    target_role: str
    current_role: str
    justification_hint: str
    approval_code: str
    now: int = 0
    ticket_opened: bool = False
    review_ready_at: int = 2
    review_checks: int = 0
    transient_pending: bool = True
    approval_confirmed: bool = False
    history: list[dict] = field(default_factory=list)

    def advance(self, steps: int) -> None:
        if steps < 0:
            raise ValueError("steps must be non-negative")
        self.now += steps

    def _record(self, entry: dict) -> None:
        self.history.append(entry | {"now": self.now})

    def status(self) -> dict:
        return {
            "now": self.now,
            "ticket_opened": self.ticket_opened,
            "review_ready_at": self.review_ready_at,
            "review_checks": self.review_checks,
            "approval_confirmed": self.approval_confirmed,
        }

    def submit_ticket(self, payload: dict | None) -> dict:
        if not payload:
            result = {"ok": False, "error": "bad_request", "message": "payload required"}
            self._record({"action": "submit_ticket", "result": result})
            return result
        if payload.get("request_id") != self.request_id:
            result = {"ok": False, "error": "unknown_request", "message": "request_id mismatch"}
            self._record({"action": "submit_ticket", "result": result})
            return result
        if payload.get("user_email") != self.user_email:
            result = {"ok": False, "error": "bad_request", "message": "user_email mismatch"}
            self._record({"action": "submit_ticket", "result": result})
            return result
        if payload.get("target_role") != self.target_role:
            result = {"ok": False, "error": "bad_request", "message": "target_role mismatch"}
            self._record({"action": "submit_ticket", "result": result})
            return result
        justification = str(payload.get("justification", ""))
        if self.justification_hint.lower() not in justification.lower():
            result = {"ok": False, "error": "insufficient_justification", "message": "ticket justification missing required hint"}
            self._record({"action": "submit_ticket", "result": result})
            return result
        self.ticket_opened = True
        result = {"ok": True, "message": "ticket accepted", "review_ready_at": self.review_ready_at}
        self._record({"action": "submit_ticket", "result": result})
        return result

    def review_status(self) -> dict:
        self.review_checks += 1
        if not self.ticket_opened:
            result = {"ok": False, "error": "ticket_required", "message": "submit ticket first"}
            self._record({"action": "review_status", "result": result})
            return result
        if self.now < self.review_ready_at:
            result = {
                "ok": False,
                "error": "review_pending",
                "retry_after": self.review_ready_at - self.now,
                "message": "review still pending",
            }
            self._record({"action": "review_status", "result": result})
            return result
        if self.transient_pending:
            self.transient_pending = False
            result = {"ok": False, "error": "temporary_failure", "message": "admin console hiccup, retry review"}
            self._record({"action": "review_status", "result": result})
            return result
        result = {
            "ok": True,
            "request_id": self.request_id,
            "recommended_action": "approve_role_change",
            "approval_code": self.approval_code,
        }
        self._record({"action": "review_status", "result": result})
        return result

    def confirm_approval(self, payload: dict | None) -> dict:
        if not payload:
            result = {"ok": False, "error": "bad_request", "message": "payload required"}
            self._record({"action": "confirm_approval", "result": result})
            return result
        if payload.get("request_id") != self.request_id:
            result = {"ok": False, "error": "unknown_request", "message": "request_id mismatch"}
            self._record({"action": "confirm_approval", "result": result})
            return result
        if payload.get("approval_code") != self.approval_code:
            result = {"ok": False, "error": "wrong_code", "message": "approval_code mismatch"}
            self._record({"action": "confirm_approval", "result": result})
            return result
        self.approval_confirmed = True
        result = {"ok": True, "token": f"{self.request_id}|{self.approval_code}"}
        self._record({"action": "confirm_approval", "result": result})
        return result
