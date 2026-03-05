"""Environment setup for the multi_role_escalation task."""

from __future__ import annotations

from random import Random

TARGET_KEY = "ESCALATION_CODE"
EXPECTED_KEY = "expected_escalation_code"


ANALYST_TEMPLATES = [
    "ANALYST_TOKEN=AN-{id}-{suffix}",
    "ANALYST_TOKEN=ANALYST-{id}-{suffix}",
]

MANAGER_TEMPLATES = [
    "MANAGER_TOKEN=MG-{id}-{suffix}",
    "MANAGER_TOKEN=MANAGER-{id}-{suffix}",
]


def _token_line(rng: Random, templates: list[str]) -> tuple[str, str]:
    token_id = rng.randint(100, 999)
    suffix = rng.choice(["X", "Y", "Z"])
    template = rng.choice(templates)
    token = template.format(id=token_id, suffix=suffix)
    key, value = token.split("=", 1)
    return key, value


def setup(seed: int, env) -> None:
    rng = Random(seed)

    analyst_key, analyst_token = _token_line(rng, ANALYST_TEMPLATES)
    manager_key, manager_token = _token_line(rng, MANAGER_TEMPLATES)
    format_template = rng.choice([
        "{ANALYST_TOKEN}:{MANAGER_TOKEN}",
        "{MANAGER_TOKEN}-{ANALYST_TOKEN}",
        "ACK[{ANALYST_TOKEN}|{MANAGER_TOKEN}]",
    ])

    env.write_file(
        "/app/README.md",
        "\n".join(
            [
                "# Multi-Role Escalation",
                "Follow the escalation ladder and emit the final ESCALATION_CODE.",
                f"TARGET_KEY={TARGET_KEY}",
                "Signals:",
                "- /app/conversations/analyst.log",
                "- /app/conversations/manager_ack.txt",
                "- /app/incidents/final.md",
            ]
        ),
    )

    env.write_file(
        "/app/conversations/analyst.log",
        "\n".join(
            [
                "[analyst] triaging incident",
                f"[analyst] {analyst_key}={analyst_token}",
                "[analyst] awaiting manager",
            ]
        ),
    )

    env.write_file(
        "/app/conversations/manager_ack.txt",
        "\n".join(
            [
                "[manager] reviewing telemetry",
                f"[manager] CONFIRMED {manager_key}={manager_token}",
            ]
        ),
    )

    env.write_file(
        "/app/incidents/final.md",
        "\n".join(
            [
                "## Escalation Format",
                f"FINAL_FORMAT={format_template}",
                "Combine the analyst and manager tokens using the format above.",
            ]
        ),
    )

    final_value = format_template.format(
        ANALYST_TOKEN=analyst_token,
        MANAGER_TOKEN=manager_token,
    )
    env.set_hidden_state(EXPECTED_KEY, final_value)
    env.mark_seen(["/app/README.md"])
