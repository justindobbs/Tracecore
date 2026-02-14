"""Tests for the task registry."""

from __future__ import annotations

from agent_bench.tasks import registry


def test_builtin_registry_lists_all_tasks(tmp_path, monkeypatch):
    sample = {
        "tasks": [
            {
                "id": "sample_task",
                "suite": "demo",
                "version": 1,
                "description": "demo",
                "path": "tasks/sample",
                "deterministic": True,
            }
        ]
    }
    manifest = tmp_path / "registry.json"
    manifest.write_text(__import__("json").dumps(sample), encoding="utf-8")

    monkeypatch.setattr(registry, "REGISTRY_PATH", manifest)
    registry._REGISTRY = None  # reset cache

    descriptor = registry.get_task_descriptor("sample_task")
    assert descriptor is not None
    assert descriptor.id == "sample_task"
    assert descriptor.version == 1
    assert descriptor.path == (tmp_path / "tasks/sample").resolve()


def test_registry_returns_none_when_missing(monkeypatch, tmp_path):
    manifest = tmp_path / "registry.json"
    manifest.write_text("{\"tasks\": []}", encoding="utf-8")

    monkeypatch.setattr(registry, "REGISTRY_PATH", manifest)
    registry._REGISTRY = None

    assert registry.get_task_descriptor("missing") is None
