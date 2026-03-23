from __future__ import annotations

from pathlib import Path


def register() -> list[dict]:
    root = Path(__file__).resolve().parent / "tasks" / "reference_echo_task"
    return [
        {
            "id": "reference_echo_task",
            "suite": "plugin_reference",
            "version": 1,
            "description": "Reference external plugin task that asks the agent to echo a seeded token.",
            "deterministic": True,
            "path": str(root),
        }
    ]
