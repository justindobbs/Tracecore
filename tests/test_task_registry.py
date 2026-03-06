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


def test_entry_point_registry_supports_plugins(tmp_path, monkeypatch):
    manifest = tmp_path / "registry.json"
    manifest.write_text("{\"tasks\": []}", encoding="utf-8")
    monkeypatch.setattr(registry, "REGISTRY_PATH", manifest)

    plugin_task_dir = tmp_path / "plugin_task"
    plugin_task_dir.mkdir()
    (plugin_task_dir / "task.yaml").write_text(
        "id: plugin_task\nsuite: plugins\nversion: 1\n", encoding="utf-8"
    )

    class FakeEntryPoint:
        def __init__(self, payload):
            self.payload = payload

        def load(self):
            return lambda: [self.payload]

    class FakeEntryPoints(list):
        def select(self, **_kwargs):
            return self

    entry_point_payload = {
        "id": "plugin_task",
        "suite": "plugins",
        "version": 1,
        "description": "demo plugin",
        "deterministic": True,
        "path": str(plugin_task_dir),
    }

    monkeypatch.setattr(
        registry.importlib.metadata,
        "entry_points",
        lambda: FakeEntryPoints([FakeEntryPoint(entry_point_payload)]),
    )

    registry.reset_registry_cache()
    descriptor = registry.get_task_descriptor("plugin_task")
    assert descriptor is not None
    assert descriptor.path == plugin_task_dir.resolve()
    assert descriptor.description == "demo plugin"


def test_registry_prefers_task_toml_and_syncs_budgets(tmp_path, monkeypatch):
    manifest = tmp_path / "registry.json"
    manifest.write_text(
        "{\"tasks\": [{\"id\": \"sample_task\", \"suite\": \"demo\", \"version\": 1, \"path\": \"tasks/sample\"}]}",
        encoding="utf-8",
    )

    task_dir = tmp_path / "tasks" / "sample"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        "\n".join(
            [
                "id = \"sample_task\"",
                "suite = \"demo\"",
                "version = 1",
                "description = \"demo task\"",
                "deterministic = true",
                "seed_behavior = \"fixed\"",
                "",
                "[budgets]",
                "steps = 10",
                "tool_calls = 4",
                "",
                "[action_surface]",
                "source = \"actions.py\"",
                "",
                "[validator]",
                "entrypoint = \"validate.py:validate\"",
                "",
                "[sandbox]",
                "filesystem_roots = [\"/app\"]",
                "network_hosts = []",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(registry, "REGISTRY_PATH", manifest)
    registry.reset_registry_cache()

    descriptor = registry.get_task_descriptor("sample_task")
    assert descriptor is not None
    assert descriptor.description == "demo task"
    assert descriptor.metadata["default_budget"]["steps"] == 10


def test_registry_rejects_deterministic_manifest_without_sandbox(tmp_path, monkeypatch):
    manifest = tmp_path / "registry.json"
    manifest.write_text(
        "{\"tasks\": [{\"id\": \"bad_task\", \"suite\": \"demo\", \"version\": 1, \"path\": \"tasks/bad_task\"}]}",
        encoding="utf-8",
    )

    task_dir = tmp_path / "tasks" / "bad_task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        "\n".join(
            [
                'id = "bad_task"',
                'suite = "demo"',
                'version = 1',
                'description = "broken deterministic task"',
                'deterministic = true',
                'seed_behavior = "fixed"',
                '',
                '[validator]',
                'entrypoint = "validate.py:validate"',
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(registry, "REGISTRY_PATH", manifest)
    registry.reset_registry_cache()

    try:
        registry.get_task_descriptor("bad_task")
        raise AssertionError("expected invalid deterministic manifest to be rejected")
    except ValueError as exc:
        assert "deterministic tasks must define sandbox table" in str(exc)


def test_validate_task_path_reports_invalid_sandbox_shape(tmp_path):
    task_dir = tmp_path / "broken_task"
    task_dir.mkdir()
    (task_dir / "setup.py").write_text("def setup(env):\n    return None\n", encoding="utf-8")
    (task_dir / "actions.py").write_text("def action_schema():\n    return {}\n", encoding="utf-8")
    (task_dir / "validate.py").write_text("def validate(output, env):\n    return {'ok': True}\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        "\n".join(
            [
                'id = "broken_task"',
                'suite = "demo"',
                'version = 1',
                'description = "broken task"',
                'deterministic = true',
                'seed_behavior = "fixed"',
                '',
                '[validator]',
                'entrypoint = "validate.py:validate"',
                '',
                '[sandbox]',
                'filesystem_roots = "/app"',
                'network_hosts = []',
            ]
        ),
        encoding="utf-8",
    )

    errors = registry.validate_task_path(task_dir)
    assert any("sandbox.filesystem_roots must be a list of strings" in err for err in errors)
