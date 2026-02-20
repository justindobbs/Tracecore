"""Tests for `agent-bench new-agent` scaffold command."""

from __future__ import annotations

import argparse

import pytest

from agent_bench import cli


def test_new_agent_creates_file(tmp_path):
    args = argparse.Namespace(name="my_patrol", output_dir=str(tmp_path), force=False)
    rc = cli._cmd_new_agent(args)
    assert rc == 0
    out = tmp_path / "my_patrol_agent.py"
    assert out.exists()
    src = out.read_text(encoding="utf-8")
    assert "class MyPatrolAgent" in src
    assert "def reset" in src
    assert "def observe" in src
    assert "def act" in src


def test_new_agent_kebab_name(tmp_path):
    args = argparse.Namespace(name="rate-limit-retry", output_dir=str(tmp_path), force=False)
    rc = cli._cmd_new_agent(args)
    assert rc == 0
    out = tmp_path / "rate_limit_retry_agent.py"
    assert out.exists()
    src = out.read_text(encoding="utf-8")
    assert "class RateLimitRetryAgent" in src


def test_new_agent_refuses_overwrite_without_force(tmp_path):
    args = argparse.Namespace(name="dup", output_dir=str(tmp_path), force=False)
    cli._cmd_new_agent(args)
    rc = cli._cmd_new_agent(args)
    assert rc == 1


def test_new_agent_force_overwrites(tmp_path):
    args = argparse.Namespace(name="dup", output_dir=str(tmp_path), force=False)
    cli._cmd_new_agent(args)
    args_force = argparse.Namespace(name="dup", output_dir=str(tmp_path), force=True)
    rc = cli._cmd_new_agent(args_force)
    assert rc == 0


def test_new_agent_stub_is_importable(tmp_path):
    import importlib.util

    args = argparse.Namespace(name="importable", output_dir=str(tmp_path), force=False)
    cli._cmd_new_agent(args)
    target = tmp_path / "importable_agent.py"
    spec = importlib.util.spec_from_file_location("importable_agent", target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    agent_cls = mod.ImportableAgent
    agent = agent_cls()
    agent.reset({})
    agent.observe(None)
    action = agent.act()
    assert isinstance(action, dict)
    assert "type" in action


def test_new_agent_stub_observe_act_cycle(tmp_path):
    import importlib.util

    args = argparse.Namespace(name="cycle_test", output_dir=str(tmp_path), force=False)
    cli._cmd_new_agent(args)
    target = tmp_path / "cycle_test_agent.py"
    spec = importlib.util.spec_from_file_location("cycle_test_agent", target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    agent = mod.CycleTestAgent()
    agent.reset({"id": "test_task", "version": 1})
    obs = {
        "last_action": None,
        "last_action_result": None,
        "remaining_steps": 10,
        "remaining_tool_calls": 10,
        "visible_state": {},
    }
    agent.observe(obs)
    action = agent.act()
    assert action.get("type") == "wait"
