"""Static known-good agent-task pairings for the `run pairing` quick-start."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnownPairing:
    name: str
    agent: str
    task: str
    description: str


PAIRINGS: list[KnownPairing] = [
    KnownPairing(
        name="filesystem_hidden_config",
        agent="agents/toy_agent.py",
        task="filesystem_hidden_config@1",
        description="Filesystem discovery baseline",
    ),
    KnownPairing(
        name="rate_limited_api",
        agent="agents/rate_limit_agent.py",
        task="rate_limited_api@1",
        description="API quota retry baseline",
    ),
    KnownPairing(
        name="rate_limited_chain",
        agent="agents/chain_agent.py",
        task="rate_limited_chain@1",
        description="Handshake + rate-limit orchestration",
    ),
    KnownPairing(
        name="ops_triage",
        agent="agents/ops_triage_agent.py",
        task="log_alert_triage@1",
        description="Operations triage reference",
    ),
    KnownPairing(
        name="log_stream_monitor",
        agent="agents/log_stream_monitor_agent.py",
        task="log_stream_monitor@1",
        description="Log stream patrol + trigger detection",
    ),
    KnownPairing(
        name="runbook_verifier",
        agent="agents/runbook_verifier_agent.py",
        task="runbook_verifier@1",
        description="Runbook execution order verification and checksum emission",
    ),
    KnownPairing(
        name="sandboxed_code_auditor",
        agent="agents/sandboxed_code_auditor_agent.py",
        task="sandboxed_code_auditor@1",
        description="Sandbox runtime audit — extract ISSUE_ID and AUDIT_CODE",
    ),
]

_BY_NAME: dict[str, KnownPairing] = {p.name: p for p in PAIRINGS}
_BY_AGENT_STEM: dict[str, KnownPairing] = {
    Path(p.agent).stem: p for p in PAIRINGS
}


def find_pairing(name: str | None, cwd: Path | None = None) -> KnownPairing | None:
    """Return the best matching pairing or None.

    Resolution order:
    1. Explicit name match.
    2. CWD auto-detect: if exactly one pairing's agent stem matches a .py file
       present in *cwd*, return it.
    """
    if name is not None:
        return _BY_NAME.get(name)

    if cwd is not None:
        matches = [
            p for p in PAIRINGS
            if (cwd / Path(p.agent).name).exists()
        ]
        if len(matches) == 1:
            return matches[0]

    return None


def list_pairings() -> list[KnownPairing]:
    return list(PAIRINGS)
