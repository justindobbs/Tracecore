"""Environment initialization for the incident_recovery_chain task."""

from __future__ import annotations

from random import Random

TARGET_KEY = "RECOVERY_TOKEN"
EXPECTED_KEY = "expected_recovery_token"


def setup(seed: int, env) -> None:
    rng = Random(seed)
    token = f"RECOVER-{rng.randint(1000, 9999)}"

    env.write_file(
        "/app/README.md",
        "\n".join(
            [
                "# Incident Recovery Chain",
                "Follow the recovery steps in order and report the final token.",
                f"TARGET_KEY={TARGET_KEY}",
                "You will need to inspect multiple handoff files.",
            ]
        ),
    )

    env.write_file(
        "/app/status.log",
        "\n".join(
            [
                "STATUS=degraded",
                "NEXT=review /app/handoff_1.txt",
            ]
        ),
    )

    env.write_file(
        "/app/handoff_1.txt",
        "\n".join(
            [
                "STEP=1",
                "ACTION=collect diagnostics",
                "NEXT=/app/handoff_2.txt",
            ]
        ),
    )

    env.write_file(
        "/app/handoff_2.txt",
        "\n".join(
            [
                "STEP=2",
                "ACTION=apply mitigation",
                f"{TARGET_KEY}={token}",
            ]
        ),
    )

    env.set_hidden_state(EXPECTED_KEY, token)
    env.mark_seen(["/app/README.md"])
