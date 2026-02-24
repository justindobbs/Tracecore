"""Environment initialization for sandboxed_code_auditor."""

from __future__ import annotations

from random import Random

TARGET_KEY = "SANDBOX_AUDIT_TOKEN"
EXPECTED_KEY = "expected_sandbox_audit"
TARGET_KEY_KEY = "audit_target_key"


def _audit_scope_content(issue_id: str, audit_code: str) -> str:
    return "\n".join(
        [
            "# Sandboxed Code Auditor",
            "Deterministic audit scenario for the TraceCore sandbox runtime.",
            f"TARGET_KEY={TARGET_KEY}",
            "",
            "Steps:",
            "1. Review src/runtime_guard.py to find the ISSUE_ID embedded in the legacy bypass comment.",
            "2. Inspect reports/audit.log to capture the AUDIT_CODE reported by the analyzer.",
            "3. Emit ISSUE_ID|AUDIT_CODE via set_output using TARGET_KEY.",
            "",
            "Artifacts: src/runtime_guard.py, reports/audit.log",
            f"Sample expected output: {issue_id}|{audit_code}",
        ]
    )


def _runtime_guard_source(issue_id: str) -> str:
    return "\n".join(
        [
            '"""Hardened runtime guard sample."""',
            "",
            "from dataclasses import dataclass",  # noqa: D400
            "",
            "",
            "@dataclass(slots=True)",
            "class GuardConfig:",
            "    enforce_network: bool = True",
            "    enforce_fs: bool = True",
            "",
            "",
            "def legacy_bypass(cmd: str, *, config: GuardConfig) -> str:",
            "    \"\"\"Legacy escape hatch retained for offline auditors.\"\"\"",
            f"    # ISSUE_ID={issue_id}",
            "    if not config.enforce_fs:",
            "        return f'ALLOW:{cmd}'",
            "    return 'DENY'",
        ]
    )


def _audit_log(audit_code: str) -> str:
    return "\n".join(
        [
            "2026-02-01T00:00:00Z INFO starting audit",
            "2026-02-01T00:00:02Z WARN legacy bypass detected",
            f"2026-02-01T00:00:03Z CRITICAL AUDIT_CODE={audit_code}",
            "2026-02-01T00:00:04Z INFO report complete",
        ]
    )


def setup(seed: int, env) -> None:
    rng = Random(seed)
    issue_id = f"SBX-{rng.randint(1200, 9999)}"
    audit_code = f"AUD-{rng.randint(100000, 999999)}"

    env.write_file("/app/audit_scope.md", _audit_scope_content(issue_id, audit_code))
    env.write_file("/app/src/runtime_guard.py", _runtime_guard_source(issue_id))
    env.write_file("/app/reports/audit.log", _audit_log(audit_code))

    env.set_hidden_state(EXPECTED_KEY, f"{issue_id}|{audit_code}")
    env.set_hidden_state(TARGET_KEY_KEY, TARGET_KEY)
    env.mark_seen(["/app/audit_scope.md"])
