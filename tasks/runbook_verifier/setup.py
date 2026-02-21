"""Environment initialization for the runbook_verifier task."""

from __future__ import annotations

from random import Random

from tasks.runbook_verifier.shared import (
    EXPECTED_KEY,
    HANDOFF_PATH,
    README_PATH,
    RUNBOOK_INDEX_PATH,
    SEQUENCE_PATH,
    TARGET_KEY,
    TIMELINE_PATH,
)

PHASE_LIBRARY = [
    ("stabilize ingress", "ING"),
    ("reroute traffic", "RER"),
    ("drain queues", "DRN"),
    ("apply hotfix", "FIX"),
    ("verify recovery", "RCV"),
    ("handoff ops", "OPS"),
]


def _write(env, path: str, lines: list[str]) -> None:
    env.write_file(path, "\n".join(lines))


def setup(seed: int, env) -> None:
    rng = Random(seed)
    selections = PHASE_LIBRARY.copy()
    rng.shuffle(selections)
    selected = selections[:3]

    phases: list[dict[str, str | int]] = []
    for idx, (label, prefix) in enumerate(selected, start=1):
        code = f"{prefix}-{rng.randint(1000, 9999)}"
        path = f"/app/phase_{idx}.md"
        phases.append({"index": idx, "label": label, "code": code, "path": path})

    ack_id = f"ACK-{rng.randint(10000, 99999)}"
    handoff_token = f"HANDOFF-{rng.randint(100000, 999999)}"

    checksum_parts = [phase["code"] for phase in phases]
    checksum_parts.append(ack_id)
    checksum_parts.append(handoff_token)
    checksum = "+".join(checksum_parts)

    _write(
        env,
        README_PATH,
        [
            "# Runbook Verifier",
            "Confirm every phase executed in order and compute the checksum.",
            f"TARGET_KEY={TARGET_KEY}",
            "Artifacts available:",
            "- runbook_index.md for phase ordering",
            "- phase_*.md for per-phase codes",
            "- sequence.log for execution status",
            "- timeline.log for ACK identifiers",
            "- handoff.md for checksum assembly",
            "",
            "Checksum format: PHASE1_CODE+PHASE2_CODE+PHASE3_CODE+ACK_ID+HANDOFF_TOKEN",
            "Use set_output to submit RUNBOOK_CHECKSUM once every component is verified.",
        ],
    )

    index_lines = ["# Runbook Index"]
    for phase in phases:
        idx = phase["index"]
        index_lines.append(f"PHASE_{idx}_PATH={phase['path']}")
        index_lines.append(f"PHASE_{idx}_NAME={phase['label']}")
    _write(env, RUNBOOK_INDEX_PATH, index_lines)

    sequence_lines = ["# Sequence log"]
    for phase in phases:
        sequence_lines.append(
            "PHASE={idx} STATUS=complete CODE={code}".format(
                idx=phase["index"], code=phase["code"]
            )
        )
    _write(env, SEQUENCE_PATH, sequence_lines)

    timeline_lines = [
        "# Incident timeline",
        "T00:00 incident declared",
        "T00:05 containment initiated",
        "T00:12 mitigation applied",
        f"ACK_ID={ack_id}",
    ]
    _write(env, TIMELINE_PATH, timeline_lines)

    _write(
        env,
        HANDOFF_PATH,
        [
            "# Final handoff",
            f"HANDOFF_TOKEN={handoff_token}",
            "Combine phase codes in index order, then append ACK_ID and HANDOFF_TOKEN",
            "Example: CODE1+CODE2+CODE3+ACK+HANDOFF",
        ],
    )

    for phase in phases:
        next_path = (
            f"/app/phase_{phase['index'] + 1}.md" if phase["index"] < len(phases) else ""
        )
        lines = [
            f"# Phase {phase['index']} :: {phase['label'].title()}",
            f"PHASE_INDEX={phase['index']}",
            f"PHASE_CODE={phase['code']}",
        ]
        if next_path:
            lines.append(f"NEXT={next_path}")
        _write(env, phase["path"], lines)

    env.set_hidden_state(EXPECTED_KEY, checksum)
    env.mark_seen([README_PATH])
