"""Environment initialization for the log_alert_triage task."""

from __future__ import annotations

from random import Random

TARGET_KEY = "ALERT_CODE"
EXPECTED_KEY = "expected_alert_code"


def setup(seed: int, env) -> None:
    rng = Random(seed)
    alert_code = f"ALERT-{rng.randint(100, 999)}"

    notes = [
        "# Log Alert Triage",
        "You are triaging a deterministic alert simulation.",
        f"TARGET_KEY={TARGET_KEY}",
        "Find the final alert code from the log artifacts and submit it via set_output.",
    ]

    env.write_file(
        "/app/README.md",
        "\n".join(notes),
    )

    env.write_file(
        "/app/service.log",
        "\n".join(
            [
                "2026-04-01T10:00:00Z INFO boot sequence started",
                "2026-04-01T10:00:03Z WARN retrying telemetry upload",
                "2026-04-01T10:00:06Z ERROR queue depth threshold exceeded",
                "2026-04-01T10:00:08Z INFO escalation file written to /app/incident.log",
            ]
        ),
    )

    env.write_file(
        "/app/incident.log",
        "\n".join(
            [
                "INCIDENT=ingest_backpressure",
                "SEVERITY=high",
                f"{TARGET_KEY}={alert_code}",
            ]
        ),
    )

    env.write_file(
        "/app/telemetry_snapshot.txt",
        "\n".join(
            [
                "queue_depth=947",
                "retry_window=2",
                "hint=check incident.log for escalation key",
            ]
        ),
    )

    env.set_hidden_state(EXPECTED_KEY, alert_code)
    env.mark_seen(["/app/README.md"])
