from __future__ import annotations

from pathlib import Path

import agent_bench.agents as bundled_agents
import agent_bench.interactive as interactive
import agent_bench.webui.app as webapp


def _bundled_agent_paths() -> set[str]:
    bundled_root = Path(bundled_agents.__file__).parent
    return {f"agents/{path.name}" for path in bundled_root.glob("*.py") if path.name != "__init__.py"}


def test_webui_falls_back_to_bundled_agents(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(webapp, "AGENTS_ROOT", tmp_path / "agents", raising=False)
    agents = webapp.get_agent_options()
    bundled = _bundled_agent_paths()
    assert agents
    assert set(agents) == bundled
    assert "agents/naive_llm_agent.py" in agents
    assert "agents/planner_agent.py" in agents
    assert "agents/cheater_agent.py" in agents
    assert "agents/dice_game_agent.py" in agents


def test_interactive_falls_back_to_bundled_agents(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(interactive, "AGENTS_ROOT", tmp_path / "agents", raising=False)
    agents = interactive._discover_agents()
    bundled = _bundled_agent_paths()
    assert agents
    assert set(agents) == bundled
