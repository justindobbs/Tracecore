"""Tests for agent_bench.integrations.autogen_adapter."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from agent_bench.integrations.autogen_adapter import _build_agent_source, generate_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_SCHEMA = {"list_dir": [], "read_file": ["path"], "set_output": ["key", "value"]}
_MINIMAL_AGENTS = [{"name": "Worker", "system_message": "Do the task."}]


def _source(**kwargs) -> str:
    defaults = dict(
        class_name="TestAgent",
        model="gpt-4o",
        agents=_MINIMAL_AGENTS,
        action_schema=_MINIMAL_SCHEMA,
        task_description="Test task.",
        max_turns=2,
        termination_keyword="DONE",
    )
    defaults.update(kwargs)
    return _build_agent_source(**defaults)


# ---------------------------------------------------------------------------
# _build_agent_source — pure generation, no external deps
# ---------------------------------------------------------------------------

def test_source_is_valid_python():
    src = _source()
    ast.parse(src)  # raises SyntaxError if invalid


def test_source_contains_class_name():
    src = _source(class_name="MyCustomAgent")
    assert "class MyCustomAgent:" in src


def test_source_contains_model():
    src = _source(model="gpt-4-turbo")
    assert "gpt-4-turbo" in src


def test_source_contains_agent_names():
    agents = [
        {"name": "Alpha", "system_message": "First."},
        {"name": "Beta", "system_message": "Second."},
    ]
    src = _source(agents=agents)
    assert '"Alpha"' in src
    assert '"Beta"' in src


def test_source_contains_action_schema():
    src = _source()
    assert "'list_dir'" in src
    assert "'read_file'" in src
    assert "'set_output'" in src


def test_source_contains_required_params():
    src = _source()
    assert "'path'" in src
    assert "'key'" in src
    assert "'value'" in src


def test_source_contains_termination_keyword():
    src = _source(termination_keyword="TERMINATE")
    assert "TERMINATE" in src


def test_source_contains_max_turns():
    src = _source(max_turns=7)
    assert "max_turns=7" in src


def test_source_has_reset_observe_act():
    src = _source()
    assert "def reset(" in src
    assert "def observe(" in src
    assert "def act(" in src


def test_source_single_agent():
    src = _source(agents=[{"name": "Solo", "system_message": "Alone."}])
    ast.parse(src)
    assert '"Solo"' in src


def test_source_special_chars_in_system_message():
    agents = [{"name": "A", "system_message": 'Say "hello" and use \\n newlines.'}]
    src = _source(agents=agents)
    ast.parse(src)  # must not produce a SyntaxError from unescaped quotes


def test_source_task_description_embedded():
    src = _source(task_description="Extract the SECRET from the vault.")
    assert "Extract the SECRET from the vault." in src


def test_source_imports_autogen():
    src = _source()
    assert "from autogen_agentchat" in src
    assert "from autogen_ext" in src


# ---------------------------------------------------------------------------
# generate_agent — file generation with a real task
# ---------------------------------------------------------------------------

def test_generate_agent_writes_file(tmp_path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        output_path=tmp_path / "out_agent.py",
    )
    assert out.exists()
    assert out.suffix == ".py"


def test_generate_agent_returns_path(tmp_path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        output_path=tmp_path / "out_agent.py",
    )
    assert isinstance(out, Path)


def test_generate_agent_valid_python(tmp_path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        output_path=tmp_path / "out_agent.py",
    )
    ast.parse(out.read_text(encoding="utf-8"))


def test_generate_agent_schema_baked_in(tmp_path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        output_path=tmp_path / "out_agent.py",
    )
    src = out.read_text(encoding="utf-8")
    # filesystem_hidden_config actions include list_dir, read_file, extract_value, set_output
    assert "'list_dir'" in src
    assert "'read_file'" in src
    assert "'set_output'" in src


def test_generate_agent_custom_class_name(tmp_path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        class_name="MyFSAgent",
        output_path=tmp_path / "out_agent.py",
    )
    src = out.read_text(encoding="utf-8")
    assert "class MyFSAgent:" in src


def test_generate_agent_custom_model(tmp_path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        model="gpt-3.5-turbo",
        output_path=tmp_path / "out_agent.py",
    )
    src = out.read_text(encoding="utf-8")
    assert "gpt-3.5-turbo" in src


def test_generate_agent_creates_parent_dirs(tmp_path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        output_path=tmp_path / "nested" / "deep" / "agent.py",
    )
    assert out.exists()


def test_generate_agent_default_agents_present(tmp_path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        output_path=tmp_path / "out_agent.py",
    )
    src = out.read_text(encoding="utf-8")
    assert '"Worker"' in src
    assert '"Supervisor"' in src


def test_generate_agent_custom_agents(tmp_path):
    out = generate_agent(
        "filesystem_hidden_config@1",
        agents=[{"name": "Planner", "system_message": "Plan."},
                {"name": "Executor", "system_message": "Execute."}],
        output_path=tmp_path / "out_agent.py",
    )
    src = out.read_text(encoding="utf-8")
    assert '"Planner"' in src
    assert '"Executor"' in src


def test_generate_agent_different_task(tmp_path):
    out = generate_agent(
        "rate_limited_api@1",
        output_path=tmp_path / "out_agent.py",
    )
    src = out.read_text(encoding="utf-8")
    ast.parse(src)
    assert "'set_output'" in src
