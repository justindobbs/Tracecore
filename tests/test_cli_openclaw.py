"""Tests for `agent-bench openclaw` and `agent-bench openclaw-export` commands."""

from __future__ import annotations

import argparse
import json

import pytest

from agent_bench import cli
from agent_bench.openclaw import (
    detect_openclaw_agent,
    export_openclaw_agent,
    scaffold_gateway_adapter,
    scaffold_openclaw_adapter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Community runbook format (agents.named + systemPromptFile)
MINIMAL_CONFIG = {
    "agents": {
        "defaults": {
            "model": {
                "primary": "anthropic/claude-sonnet-4-5",
                "fallbacks": ["openai/gpt-5-mini"],
            }
        },
        "named": {
            "researcher": {
                "model": {
                    "primary": "kimi-coding/k2p5",
                    "fallbacks": ["openai/gpt-5-mini"],
                },
                "systemPromptFile": "workspace/agents/researcher.md",
            }
        },
    }
}

# Canonical format (official OpenClaw docs: agents.list + workspace/AGENTS.md)
CANONICAL_CONFIG = {
    "agents": {
        "defaults": {
            "model": {
                "primary": "anthropic/claude-sonnet-4-5",
                "fallbacks": ["openai/gpt-5-mini"],
            }
        },
        "list": [
            {
                "id": "main",
                "default": True,
                "model": "anthropic/claude-opus-4-6",
                "workspace": "",  # filled in by fixture
            }
        ],
    }
}


@pytest.fixture()
def openclaw_workspace(tmp_path):
    """Create a minimal OpenClaw workspace using the runbook agents.named format."""
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(json.dumps(MINIMAL_CONFIG), encoding="utf-8")

    prompt_dir = tmp_path / "workspace" / "agents"
    prompt_dir.mkdir(parents=True)
    prompt_file = prompt_dir / "researcher.md"
    prompt_file.write_text(
        "You are a researcher agent. Research topics thoroughly.", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def canonical_workspace(tmp_path):
    """Create a minimal OpenClaw workspace using the canonical agents.list format."""
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    agents_md = workspace_dir / "AGENTS.md"
    agents_md.write_text(
        "You are the main OpenClaw agent. Be helpful and precise.", encoding="utf-8"
    )

    config = json.loads(json.dumps(CANONICAL_CONFIG))
    config["agents"]["list"][0]["workspace"] = str(workspace_dir)
    (tmp_path / "openclaw.json").write_text(json.dumps(config), encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# detect_openclaw_agent — runbook format (agents.named)
# ---------------------------------------------------------------------------


def test_detect_reads_openclaw_json(openclaw_workspace):
    meta = detect_openclaw_agent(openclaw_workspace, "researcher")
    assert meta is not None
    assert meta["id"] == "researcher"
    assert meta["model"]["primary"] == "kimi-coding/k2p5"
    assert meta["prompt_file"] is not None
    assert "researcher" in str(meta["prompt_file"])
    assert "researcher agent" in meta["prompt_text"]


def test_detect_returns_none_for_missing_agent(openclaw_workspace):
    meta = detect_openclaw_agent(openclaw_workspace, "nonexistent")
    assert meta is None


def test_detect_returns_none_when_no_config(tmp_path):
    meta = detect_openclaw_agent(tmp_path, "researcher")
    assert meta is None


def test_detect_auto_selects_single_agent(openclaw_workspace):
    meta = detect_openclaw_agent(openclaw_workspace, None)
    assert meta is not None
    assert meta["id"] == "researcher"


def test_detect_returns_none_for_ambiguous_agents(tmp_path):
    config = {
        "agents": {
            "named": {
                "monitor": {"systemPromptFile": "a.md"},
                "researcher": {"systemPromptFile": "b.md"},
            }
        }
    }
    (tmp_path / "openclaw.json").write_text(json.dumps(config), encoding="utf-8")
    meta = detect_openclaw_agent(tmp_path, None)
    assert meta is None


# ---------------------------------------------------------------------------
# detect_openclaw_agent — canonical format (agents.list + AGENTS.md)
# ---------------------------------------------------------------------------


def test_detect_canonical_list_format(canonical_workspace):
    meta = detect_openclaw_agent(canonical_workspace, "main")
    assert meta is not None
    assert meta["id"] == "main"
    assert meta["model"]["primary"] == "anthropic/claude-opus-4-6"
    assert meta["prompt_file"] is not None
    assert meta["prompt_file"].name == "AGENTS.md"
    assert "main OpenClaw agent" in meta["prompt_text"]


def test_detect_canonical_auto_selects_single(canonical_workspace):
    meta = detect_openclaw_agent(canonical_workspace, None)
    assert meta is not None
    assert meta["id"] == "main"


def test_detect_canonical_model_string_normalised(canonical_workspace):
    """Model given as a plain string should be normalised to {primary, fallbacks}."""
    meta = detect_openclaw_agent(canonical_workspace, "main")
    assert isinstance(meta["model"], dict)
    assert "primary" in meta["model"]


def test_detect_canonical_default_flag(tmp_path):
    """When multiple list entries exist, the one with default=True is chosen."""
    workspace_a = tmp_path / "ws_a"
    workspace_b = tmp_path / "ws_b"
    workspace_a.mkdir()
    workspace_b.mkdir()
    (workspace_b / "AGENTS.md").write_text("Default agent prompt.", encoding="utf-8")

    config = {
        "agents": {
            "list": [
                {"id": "monitor", "workspace": str(workspace_a)},
                {"id": "main", "default": True, "workspace": str(workspace_b)},
            ]
        }
    }
    (tmp_path / "openclaw.json").write_text(json.dumps(config), encoding="utf-8")
    meta = detect_openclaw_agent(tmp_path, None)
    assert meta is not None
    assert meta["id"] == "main"
    assert "Default agent" in meta["prompt_text"]


# ---------------------------------------------------------------------------
# scaffold_openclaw_adapter
# ---------------------------------------------------------------------------


def test_scaffold_creates_adapter(openclaw_workspace):
    meta = detect_openclaw_agent(openclaw_workspace, "researcher")
    path = scaffold_openclaw_adapter(meta, openclaw_workspace)
    assert path.exists()
    assert path.name == "researcher_adapter_agent.py"
    src = path.read_text(encoding="utf-8")
    assert "class ResearcherAdapterAgent" in src
    assert "def reset" in src
    assert "def observe" in src
    assert "def act" in src
    assert "AGENT_ID" in src
    assert "researcher" in src


def test_scaffold_adapter_is_importable(openclaw_workspace):
    import importlib.util

    meta = detect_openclaw_agent(openclaw_workspace, "researcher")
    path = scaffold_openclaw_adapter(meta, openclaw_workspace)
    spec = importlib.util.spec_from_file_location("researcher_adapter_agent", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    agent = mod.ResearcherAdapterAgent()
    agent.reset({})
    agent.observe({"remaining_steps": 10, "remaining_tool_calls": 10})
    action = agent.act()
    assert isinstance(action, dict)
    assert "type" in action


def test_scaffold_gateway_adapter(openclaw_workspace):
    meta = detect_openclaw_agent(openclaw_workspace, "researcher")
    path = scaffold_gateway_adapter(meta, openclaw_workspace)
    assert path.exists()
    assert path.name == "researcher_gateway_adapter_agent.py"
    src = path.read_text(encoding="utf-8")
    assert "class ResearcherGatewayAdapterAgent" in src
    assert "agent_wait" in src
    assert "AGENT_ID" in src


# ---------------------------------------------------------------------------
# export_openclaw_agent
# ---------------------------------------------------------------------------

FAKE_RUN = {
    "run_id": "abc123",
    "task_ref": "filesystem_hidden_config@1",
    "seed": 0,
    "failure_type": None,
    "started_at": "2026-02-18T20:00:00+00:00",
    "finished_at": "2026-02-18T20:00:05+00:00",
}


def test_export_writes_manifest(openclaw_workspace, tmp_path):
    meta = detect_openclaw_agent(openclaw_workspace, "researcher")
    adapter_path = scaffold_openclaw_adapter(meta, openclaw_workspace)
    out_dir = tmp_path / "export"

    bundle_dir = export_openclaw_agent(
        agent_meta=meta,
        adapter_path=adapter_path,
        last_run=FAKE_RUN,
        out_dir=out_dir,
    )

    assert bundle_dir.exists()
    manifest = json.loads((bundle_dir / "manifest.json").read_text())
    assert manifest["agent_id"] == "researcher"
    assert manifest["task_ref"] == "filesystem_hidden_config@1"
    assert manifest["seed"] == 0
    assert manifest["run_id"] == "abc123"
    assert "adapter_agent.py" in [f.name for f in bundle_dir.iterdir()]
    assert "README.md" in [f.name for f in bundle_dir.iterdir()]


def test_export_copies_prompt_file(openclaw_workspace, tmp_path):
    meta = detect_openclaw_agent(openclaw_workspace, "researcher")
    adapter_path = scaffold_openclaw_adapter(meta, openclaw_workspace)
    out_dir = tmp_path / "export"

    bundle_dir = export_openclaw_agent(
        agent_meta=meta,
        adapter_path=adapter_path,
        last_run=FAKE_RUN,
        out_dir=out_dir,
    )

    assert (bundle_dir / "openclaw_agent.md").exists()
    content = (bundle_dir / "openclaw_agent.md").read_text()
    assert "researcher agent" in content


def test_export_includes_gateway_adapter(openclaw_workspace, tmp_path):
    meta = detect_openclaw_agent(openclaw_workspace, "researcher")
    adapter_path = scaffold_openclaw_adapter(meta, openclaw_workspace)
    gw_path = scaffold_gateway_adapter(meta, openclaw_workspace)
    out_dir = tmp_path / "export"

    bundle_dir = export_openclaw_agent(
        agent_meta=meta,
        adapter_path=adapter_path,
        last_run=FAKE_RUN,
        out_dir=out_dir,
        gateway_adapter_path=gw_path,
    )

    assert (bundle_dir / "gateway_adapter_agent.py").exists()


# ---------------------------------------------------------------------------
# _cmd_openclaw_export — export blocked without passing run
# ---------------------------------------------------------------------------


def test_export_blocked_without_passing_run(openclaw_workspace, monkeypatch):
    meta = detect_openclaw_agent(openclaw_workspace, "researcher")
    scaffold_openclaw_adapter(meta, openclaw_workspace)

    monkeypatch.chdir(openclaw_workspace)
    monkeypatch.setattr(cli, "list_runs", lambda **_: [])

    args = argparse.Namespace(
        agent_id="researcher",
        out_dir=str(openclaw_workspace / "export"),
        _config=None,
    )
    rc = cli._cmd_openclaw_export(args)
    assert rc == 1


def test_export_blocked_when_adapter_missing(openclaw_workspace, monkeypatch):
    monkeypatch.chdir(openclaw_workspace)

    args = argparse.Namespace(
        agent_id="researcher",
        out_dir=str(openclaw_workspace / "export"),
        _config=None,
    )
    rc = cli._cmd_openclaw_export(args)
    assert rc == 1


# ---------------------------------------------------------------------------
# _cmd_openclaw — scaffold on first run
# ---------------------------------------------------------------------------


def test_openclaw_cmd_scaffolds_on_first_run(openclaw_workspace, monkeypatch):
    monkeypatch.chdir(openclaw_workspace)

    args = argparse.Namespace(
        agent_id="researcher",
        task="filesystem_hidden_config@1",
        seed=0,
        timeout=None,
        gateway=False,
        _config=None,
    )
    rc = cli._cmd_openclaw(args)
    assert rc == 0
    assert (openclaw_workspace / "researcher_adapter_agent.py").exists()


def test_openclaw_cmd_returns_1_when_no_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    args = argparse.Namespace(
        agent_id="researcher",
        task="filesystem_hidden_config@1",
        seed=0,
        timeout=None,
        gateway=False,
        _config=None,
    )
    rc = cli._cmd_openclaw(args)
    assert rc == 1
