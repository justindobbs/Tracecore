"""Tests for agent_bench.runner.episode_config."""

from __future__ import annotations

import json

import pytest

from agent_bench.runner.episode_config import EpisodeConfig, load_episode_config


_MINIMAL = {
    "agent": "agents/toy_agent.py",
    "task_ref": "filesystem_hidden_config@1",
}

_FULL = {
    "agent": "agents/lc_agent.py",
    "task_ref": "log_alert_triage@1",
    "seed": 7,
    "model": "gpt-4o",
    "provider": "openai",
    "budget_override": {"steps": 50, "tool_calls": 20},
    "wall_clock_timeout_s": 120,
    "metadata": {"experiment": "gpt4o-baseline", "ci_run": "123"},
    "schema_version": "1",
}


class TestLoadEpisodeConfig:
    def test_minimal_required_fields(self):
        cfg = load_episode_config(_MINIMAL)
        assert cfg.agent == "agents/toy_agent.py"
        assert cfg.task_ref == "filesystem_hidden_config@1"
        assert cfg.seed == 0
        assert cfg.model is None
        assert cfg.provider is None
        assert cfg.budget_override == {}
        assert cfg.wall_clock_timeout_s is None
        assert cfg.metadata == {}

    def test_full_round_trip(self):
        cfg = load_episode_config(_FULL)
        assert cfg.agent == "agents/lc_agent.py"
        assert cfg.task_ref == "log_alert_triage@1"
        assert cfg.seed == 7
        assert cfg.model == "gpt-4o"
        assert cfg.provider == "openai"
        assert cfg.budget_override == {"steps": 50, "tool_calls": 20}
        assert cfg.wall_clock_timeout_s == 120
        assert cfg.metadata == {"experiment": "gpt4o-baseline", "ci_run": "123"}

    def test_missing_agent_raises(self):
        with pytest.raises(ValueError, match="agent"):
            load_episode_config({"task_ref": "foo@1"})

    def test_missing_task_ref_raises(self):
        with pytest.raises(ValueError, match="task_ref"):
            load_episode_config({"agent": "agents/a.py"})

    def test_empty_agent_raises(self):
        with pytest.raises(ValueError, match="agent"):
            load_episode_config({"agent": "", "task_ref": "foo@1"})

    def test_bad_seed_type_raises(self):
        with pytest.raises(ValueError, match="seed"):
            load_episode_config({**_MINIMAL, "seed": "notanint"})

    def test_bad_model_type_raises(self):
        with pytest.raises(ValueError, match="model"):
            load_episode_config({**_MINIMAL, "model": 42})

    def test_bad_provider_type_raises(self):
        with pytest.raises(ValueError, match="provider"):
            load_episode_config({**_MINIMAL, "provider": 99})

    def test_bad_budget_override_raises(self):
        with pytest.raises(ValueError, match="budget_override"):
            load_episode_config({**_MINIMAL, "budget_override": "not_a_dict"})

    def test_budget_override_negative_raises(self):
        with pytest.raises(ValueError, match="budget_override"):
            load_episode_config({**_MINIMAL, "budget_override": {"steps": -1}})

    def test_bad_timeout_type_raises(self):
        with pytest.raises(ValueError, match="wall_clock_timeout_s"):
            load_episode_config({**_MINIMAL, "wall_clock_timeout_s": "120s"})

    def test_not_a_dict_raises(self):
        with pytest.raises(ValueError, match="JSON object"):
            load_episode_config([])


class TestEpisodeConfigDataclass:
    def test_to_dict_round_trip(self):
        cfg = load_episode_config(_FULL)
        d = cfg.to_dict()
        assert d["agent"] == _FULL["agent"]
        assert d["budget_override"] == _FULL["budget_override"]

    def test_to_json_valid(self):
        cfg = load_episode_config(_MINIMAL)
        s = cfg.to_json()
        parsed = json.loads(s)
        assert parsed["agent"] == "agents/toy_agent.py"

    def test_write_and_from_file(self, tmp_path):
        cfg = load_episode_config(_FULL)
        path = cfg.write(tmp_path / "ep.json")
        assert path.exists()
        loaded = EpisodeConfig.from_file(path)
        assert loaded.agent == cfg.agent
        assert loaded.seed == cfg.seed
        assert loaded.budget_override == cfg.budget_override

    def test_schema_version_preserved(self):
        cfg = load_episode_config(_FULL)
        assert cfg.schema_version == "1"

    def test_default_schema_version(self):
        cfg = load_episode_config(_MINIMAL)
        assert cfg.schema_version == "1"


class TestEffectiveBudget:
    def test_no_override_returns_task_default(self):
        cfg = EpisodeConfig(agent="a.py", task_ref="t@1", budget_override={})
        result = cfg.effective_budget({"steps": 100, "tool_calls": 40})
        assert result == {"steps": 100, "tool_calls": 40}

    def test_override_replaces_keys(self):
        cfg = EpisodeConfig(agent="a.py", task_ref="t@1", budget_override={"steps": 20})
        result = cfg.effective_budget({"steps": 100, "tool_calls": 40})
        assert result["steps"] == 20
        assert result["tool_calls"] == 40

    def test_override_does_not_mutate_task_default(self):
        task_default = {"steps": 100, "tool_calls": 40}
        cfg = EpisodeConfig(agent="a.py", task_ref="t@1", budget_override={"steps": 20})
        cfg.effective_budget(task_default)
        assert task_default["steps"] == 100

    def test_zero_override_ignored(self):
        cfg = EpisodeConfig(agent="a.py", task_ref="t@1", budget_override={"steps": 0})
        result = cfg.effective_budget({"steps": 100, "tool_calls": 40})
        assert result["steps"] == 100
