"""Episode configuration schema for swapping models/tools under budgets.

An *episode config* is a lightweight, serialisable dict that parameterises a
single TraceCore run without touching the task manifest.  It lets teams:

- Pin a specific model + provider for reproducibility comparisons.
- Override per-run budgets (steps, tool_calls, wall_clock_timeout_s).
- Attach free-form metadata (experiment tags, CI run IDs, etc.) that flows
  into the run artifact and OTLP export.

Typical usage::

    from agent_bench.runner.episode_config import EpisodeConfig, load_episode_config

    cfg = EpisodeConfig(
        agent="agents/my_agent.py",
        task_ref="filesystem_hidden_config@1",
        seed=42,
        model="gpt-4o",
        provider="openai",
        budget_override={"steps": 50, "tool_calls": 20},
        metadata={"experiment": "gpt4o-vs-mini"},
    )

    # Serialise to/from JSON
    import json
    roundtripped = load_episode_config(json.loads(cfg.to_json()))

    # Load from a file
    cfg2 = EpisodeConfig.from_file("episode.json")
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = "1"


@dataclass
class EpisodeConfig:
    """Serialisable configuration for a single TraceCore episode.

    Parameters
    ----------
    agent:
        Path to the agent file (passed directly to the runner).
    task_ref:
        Task reference string in ``<id>@<version>`` format.
    seed:
        Deterministic seed for the episode.
    model:
        Optional model name hint forwarded to the agent via ``task_spec``.
    provider:
        Optional provider name hint (``"openai"``, ``"anthropic"``, etc.).
    budget_override:
        Optional dict with ``steps`` and/or ``tool_calls`` keys that
        override the task's ``default_budget`` for this episode.
    wall_clock_timeout_s:
        Optional wall-clock timeout in seconds (passed to ``--timeout``).
    metadata:
        Arbitrary key/value pairs that are merged into the run artifact's
        top-level fields and forwarded to OTLP span attributes.
    schema_version:
        Internal schema version string; do not set manually.
    """

    agent: str
    task_ref: str
    seed: int = 0
    model: str | None = None
    provider: str | None = None
    budget_override: dict[str, int] = field(default_factory=dict)
    wall_clock_timeout_s: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = _SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def write(self, path: str | Path) -> Path:
        """Write this config to *path* and return the resolved Path."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_json(), encoding="utf-8")
        return p

    @classmethod
    def from_file(cls, path: str | Path) -> "EpisodeConfig":
        """Load an EpisodeConfig from a JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return load_episode_config(data)

    def effective_budget(self, task_default_budget: dict) -> dict:
        """Merge task default budget with any per-episode override.

        Returns a new dict; does not mutate either input.
        """
        merged = dict(task_default_budget)
        for key, value in (self.budget_override or {}).items():
            if isinstance(value, int) and value > 0:
                merged[key] = value
        return merged


def load_episode_config(data: dict) -> EpisodeConfig:
    """Validate and deserialise a raw dict into an EpisodeConfig.

    Raises
    ------
    ValueError
        If required fields are missing or have wrong types.
    """
    if not isinstance(data, dict):
        raise ValueError("episode config must be a JSON object")

    agent = data.get("agent")
    task_ref = data.get("task_ref")
    if not isinstance(agent, str) or not agent:
        raise ValueError("episode config missing required string field: 'agent'")
    if not isinstance(task_ref, str) or not task_ref:
        raise ValueError("episode config missing required string field: 'task_ref'")

    seed = data.get("seed", 0)
    if not isinstance(seed, int):
        raise ValueError("episode config 'seed' must be an integer")

    model = data.get("model")
    if model is not None and not isinstance(model, str):
        raise ValueError("episode config 'model' must be a string or null")

    provider = data.get("provider")
    if provider is not None and not isinstance(provider, str):
        raise ValueError("episode config 'provider' must be a string or null")

    budget_override = data.get("budget_override") or {}
    if not isinstance(budget_override, dict):
        raise ValueError("episode config 'budget_override' must be an object or null")
    for k, v in budget_override.items():
        if not isinstance(v, int) or v <= 0:
            raise ValueError(
                f"episode config 'budget_override.{k}' must be a positive integer, got {v!r}"
            )

    timeout = data.get("wall_clock_timeout_s")
    if timeout is not None and not isinstance(timeout, int):
        raise ValueError("episode config 'wall_clock_timeout_s' must be an integer or null")

    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("episode config 'metadata' must be an object or null")

    return EpisodeConfig(
        agent=agent,
        task_ref=task_ref,
        seed=seed,
        model=model,
        provider=provider,
        budget_override=budget_override,
        wall_clock_timeout_s=timeout,
        metadata=metadata,
        schema_version=str(data.get("schema_version", _SCHEMA_VERSION)),
    )
