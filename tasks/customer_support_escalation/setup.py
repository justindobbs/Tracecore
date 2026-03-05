"""Environment setup for the customer_support_escalation task."""

from __future__ import annotations

import json
from random import Random

TARGET_KEY = "ESCALATION_CODE"
EXPECTED_KEY = "expected_escalation_code"

SERVICES = ["billing-api", "analytics-pipeline", "auth-gateway"]
SEVERITIES = ["SEV1", "SEV2"]
CHANNELS = ["slack", "pager", "email"]
MANAGERS = ["A. Quinn", "L. Rivera", "S. Banerjee"]


def setup(seed: int, env) -> None:
    rng = Random(seed)

    service = rng.choice(SERVICES)
    severity = rng.choice(SEVERITIES)
    ack_channel = rng.choice(CHANNELS)
    manager = rng.choice(MANAGERS)
    escalation_code = f"ESC-{rng.randint(100, 999)}-{rng.choice(['A', 'B', 'C'])}"

    env.write_file(
        "/app/README.md",
        "\n".join(
            [
                "# Customer Support Escalation",
                "Follow the documented escalation ladder before emitting the final code.",
                f"TARGET_KEY={TARGET_KEY}",
                "Artifacts:",
                "- /app/tickets/ticket.json",
                "- /app/conversations/manager_ack.txt",
                "- /app/policies/escalation.md",
            ]
        ),
    )

    ticket = {
        "service": service,
        "severity": severity,
        "channel": ack_channel,
        "manager": manager,
        "status": "awaiting_manager_ack",
    }
    env.write_file("/app/tickets/ticket.json", json.dumps(ticket, indent=2))

    transcript_lines = [
        f"[{ack_channel}] responder -> manager: Requesting approval for {service}",
        f"[{ack_channel}] manager -> responder: Need policy confirmation for {severity}",
        f"[{ack_channel}] manager -> responder: CONFIRMED {TARGET_KEY}={escalation_code}",
    ]
    env.write_file("/app/conversations/manager_ack.txt", "\n".join(transcript_lines))

    policy_doc = [
        "# Escalation Policy",
        "1. Validate severity mapping.",
        "2. Capture manager confirmation containing the canonical ESCALATION_CODE.",
        "3. Submit only the confirmed value from the manager transcript.",
    ]
    env.write_file("/app/policies/escalation.md", "\n".join(policy_doc))

    env.set_hidden_state(EXPECTED_KEY, escalation_code)
    env.mark_seen(["/app/README.md"])
