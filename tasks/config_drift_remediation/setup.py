"""Environment initialization for the config_drift_remediation task."""

from __future__ import annotations

from random import Random

TARGET_KEY = "DRIFT_PATCH"
EXPECTED_KEY = "expected_patch"


def setup(seed: int, env) -> None:
    rng = Random(seed)
    desired_limit = rng.choice([250, 300, 350])
    desired_mode = rng.choice(["safe", "resilient", "hardened"])

    env.write_file(
        "/app/README.md",
        "\n".join(
            [
                "# Config Drift Remediation",
                "Compare desired vs live config and output the remediation patch.",
                f"TARGET_KEY={TARGET_KEY}",
                "Submit the full line that corrects the drift (KEY=VALUE).",
            ]
        ),
    )

    env.write_file(
        "/app/desired.conf",
        "\n".join(
            [
                f"MAX_CONN={desired_limit}",
                f"MODE={desired_mode}",
                "RETRY_WINDOW=3",
            ]
        ),
    )

    env.write_file(
        "/app/live.conf",
        "\n".join(
            [
                f"MAX_CONN={desired_limit // 2}",
                f"MODE={desired_mode}",
                "RETRY_WINDOW=3",
            ]
        ),
    )

    env.write_file(
        "/app/notes.txt",
        "\n".join(
            [
                "drift_detector: mismatch detected in MAX_CONN",
                "hint: desired.conf is canonical",
            ]
        ),
    )

    env.set_hidden_state(EXPECTED_KEY, f"MAX_CONN={desired_limit}")
    env.mark_seen(["/app/README.md"])
