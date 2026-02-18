"""Contract tests for KnownPairing registry.

Every entry in PAIRINGS must reference:
  - an agent file that exists on disk
  - a task directory (with task.toml or task.yaml) that exists on disk

These tests catch stale entries after renames or deletions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_bench.pairings import PAIRINGS, KnownPairing

REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------

def test_pairings_list_is_non_empty():
    assert len(PAIRINGS) > 0, "PAIRINGS must contain at least one entry"


def test_all_pairings_have_non_empty_fields():
    for p in PAIRINGS:
        assert p.name, f"Pairing has empty name: {p!r}"
        assert p.agent, f"Pairing {p.name!r} has empty agent"
        assert p.task, f"Pairing {p.name!r} has empty task"
        assert p.description, f"Pairing {p.name!r} has empty description"


def test_pairing_names_are_unique():
    names = [p.name for p in PAIRINGS]
    assert len(names) == len(set(names)), f"Duplicate pairing names: {names}"


def test_task_refs_have_version_suffix():
    for p in PAIRINGS:
        assert "@" in p.task, (
            f"Pairing {p.name!r} task ref {p.task!r} is missing version suffix (expected 'id@N')"
        )


# ---------------------------------------------------------------------------
# On-disk existence checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pairing", PAIRINGS, ids=lambda p: p.name)
def test_agent_file_exists(pairing: KnownPairing):
    agent_path = REPO_ROOT / pairing.agent
    assert agent_path.exists(), (
        f"Pairing {pairing.name!r}: agent file not found at {agent_path}"
    )


@pytest.mark.parametrize("pairing", PAIRINGS, ids=lambda p: p.name)
def test_task_directory_exists(pairing: KnownPairing):
    task_id = pairing.task.split("@")[0]
    task_dir = REPO_ROOT / "tasks" / task_id
    assert task_dir.is_dir(), (
        f"Pairing {pairing.name!r}: task directory not found at {task_dir}"
    )


@pytest.mark.parametrize("pairing", PAIRINGS, ids=lambda p: p.name)
def test_task_manifest_exists(pairing: KnownPairing):
    task_id = pairing.task.split("@")[0]
    task_dir = REPO_ROOT / "tasks" / task_id
    has_manifest = (task_dir / "task.toml").exists() or (task_dir / "task.yaml").exists()
    assert has_manifest, (
        f"Pairing {pairing.name!r}: no task.toml or task.yaml in {task_dir}"
    )
