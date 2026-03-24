"""Tests for the `agent-bench tasks validate` CLI command."""

from __future__ import annotations

import argparse
import json

from agent_bench import cli


def test_cli_tasks_validate_paths_and_registry(monkeypatch, capsys):
    def fake_validate_task_path(path):
        assert path.as_posix() == "tasks/sample"
        return ["missing manifest"]

    def fake_validate_registry_entries():
        return ["registry error"]

    monkeypatch.setattr(cli, "validate_task_path", fake_validate_task_path)
    monkeypatch.setattr(cli, "validate_registry_entries", fake_validate_registry_entries)

    args = argparse.Namespace(path=["tasks/sample"], registry=True)
    exit_code = cli._cmd_tasks_validate(args)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert "registry error" in payload["errors"]
    assert any("missing manifest" in err for err in payload["errors"])


def test_cli_tasks_validate_defaults_to_registry(monkeypatch, capsys):
    monkeypatch.setattr(cli, "validate_registry_entries", lambda: [])

    args = argparse.Namespace(path=None, registry=False)
    exit_code = cli._cmd_tasks_validate(args)

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"valid": True, "errors": []}


def test_cli_tasks_validate_surfaces_manifest_validation_errors(tmp_path, capsys):
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

    args = argparse.Namespace(path=[str(task_dir)], registry=False)
    exit_code = cli._cmd_tasks_validate(args)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert any("sandbox.filesystem_roots must be a list of strings" in err for err in payload["errors"])


def test_cli_tasks_quality_gate_passes(monkeypatch, capsys):
    monkeypatch.setattr(cli, "validate_registry_entries", lambda: [])

    class _Descriptor:
        path = "tasks/sample"

    monkeypatch.setattr(
        cli,
        "_cmd_tasks_lint",
        lambda args: print(json.dumps({"ok": True, "errors": [], "warnings": [], "summary": "0 error(s), 0 warning(s)"})),
    )

    from agent_bench.tasks import registry as registry_mod

    monkeypatch.setattr(registry_mod, "parse_spec_freeze_task_refs", lambda path=None: ["sample_task@1"])
    monkeypatch.setattr(registry_mod, "validate_spec_freeze_entries", lambda path=None: [])
    monkeypatch.setattr(registry_mod, "get_task_descriptor", lambda task_id, version=None: _Descriptor())

    args = argparse.Namespace(spec_freeze=None)
    exit_code = cli._cmd_tasks_quality_gate(args)

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["frozen_task_refs"] == ["sample_task@1"]
    assert payload["registry_errors"] == []
    assert payload["lint_errors"] == []


def test_cli_tasks_quality_gate_fails_for_missing_frozen_task(monkeypatch, capsys):
    monkeypatch.setattr(cli, "validate_registry_entries", lambda: [])

    from agent_bench.tasks import registry as registry_mod

    monkeypatch.setattr(registry_mod, "parse_spec_freeze_task_refs", lambda path=None: ["missing_task@1"])
    monkeypatch.setattr(
        registry_mod,
        "validate_spec_freeze_entries",
        lambda path=None: ["frozen task missing from registry: missing_task@1"],
    )
    monkeypatch.setattr(registry_mod, "get_task_descriptor", lambda task_id, version=None: None)

    args = argparse.Namespace(spec_freeze=None)
    exit_code = cli._cmd_tasks_quality_gate(args)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["frozen_errors"] == ["frozen task missing from registry: missing_task@1"]
