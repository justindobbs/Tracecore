"""Environment setup for the security_incident_triage task."""

from __future__ import annotations

import json
from random import Random

TARGET_KEY = "BREACH_TOKEN"
EXPECTED_KEY = "expected_breach_token"


def _noise_event(rng: Random) -> str:
    catalog = [
        "INFO ids heartbeat ok",
        "WARN correlation backlog rising",
        "INFO analyst note archived",
        "ERROR transient socket reset (suppressed)",
        "WARN queue depth %.2f" % (rng.random() * 10),
        "INFO sampling window rotated",
    ]
    return rng.choice(catalog)


def setup(seed: int, env) -> None:
    rng = Random(seed)

    breach_token = f"BR-{rng.randint(1000, 9999)}-{rng.randint(10, 99)}"
    decoy_token = f"BR-{rng.randint(1000, 9999)}-{rng.randint(10, 99)}"
    if decoy_token == breach_token:
        decoy_token = f"BR-{rng.randint(2000, 9999)}-{rng.randint(10, 99)}"

    env.write_file(
        "/app/README.md",
        "\n".join(
            [
                "# Security Incident Triage",
                "Investigate the provided incident bundle and submit the confirmed BREACH_TOKEN.",
                f"TARGET_KEY={TARGET_KEY}",
                "Signals:",
                "- /app/logs/ids.log",
                "- /app/findings/triage.txt",
                "- /app/incidents/incident.md",
            ]
        ),
    )

    ids_entries = [
        _noise_event(rng)
        for _ in range(3)
    ]
    ids_entries.append(f"CRITICAL indicator candidate_token={decoy_token}")
    ids_entries.extend(_noise_event(rng) for _ in range(2))
    env.write_file(
        "/app/logs/ids.log",
        "\n".join(ids_entries),
    )

    findings = {
        "stage": "triage",
        "alerts": [
            {"type": "ids", "status": "noise"},
            {"type": "sandbox", "status": "requires_review", "token": decoy_token},
        ],
        "next": "escalate",
    }
    env.write_file("/app/findings/triage.json", json.dumps(findings, indent=2))

    incident_md = [
        "# Incident escalation",
        "The CSIRT review validated the breach indicator only after analyst confirmation.",
        "",
        f"CONFIRMED {TARGET_KEY}={breach_token}",
        "Do not submit tokens that appear before this section.",
    ]
    env.write_file("/app/incidents/incident.md", "\n".join(incident_md))

    env.set_hidden_state(EXPECTED_KEY, breach_token)
    env.mark_seen(["/app/README.md"])
