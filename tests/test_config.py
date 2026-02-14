"""Unit tests for agent_bench.config."""

from __future__ import annotations

import textwrap

import pytest

from agent_bench import config


def test_load_config_reads_defaults_and_agent_block(tmp_path):
    cfg_text = textwrap.dedent(
        """
        [defaults]
        agent = "agents/toy_agent.py"
        task = "filesystem_hidden_config@1"
        seed = 123

        [agent."agents/rate_limit_agent.py"]
        task = "rate_limited_api@1"
        seed = 99
        """
    ).strip()
    cfg_path = tmp_path / "agent-bench.toml"
    cfg_path.write_text(cfg_text, encoding="utf-8")

    loaded = config.load_config(cfg_path)
    assert loaded is not None
    assert loaded.get_default_agent() == "agents/toy_agent.py"
    assert loaded.get_default_task() == "filesystem_hidden_config@1"
    assert loaded.get_default_seed() == 123

    scoped_seed = loaded.get_seed(agent="agents/rate_limit_agent.py")
    scoped_task = loaded.get_task(agent="agents/rate_limit_agent.py")
    assert scoped_seed == 99
    assert scoped_task == "rate_limited_api@1"


def test_load_config_missing_file_optional(tmp_path):
    assert config.load_config(tmp_path / "missing.toml") is None


def test_load_config_missing_file_required(tmp_path):
    with pytest.raises(config.ConfigError):
        config.load_config(tmp_path / "missing.toml", require=True)
