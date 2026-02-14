"""agent-bench.toml configuration loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for 3.10
    import tomli as tomllib  # type: ignore[assignment]

DEFAULT_FILENAMES = ("agent-bench.toml", "agent_bench.toml")
ENV_CONFIG_VAR = "AGENT_BENCH_CONFIG"


class ConfigError(RuntimeError):
    """Raised when the agent-bench TOML config cannot be loaded."""


@dataclass(slots=True)
class AgentBenchConfig:
    """Thin wrapper providing helper accessors for config values."""

    path: Path
    data: dict[str, Any]

    @property
    def defaults(self) -> dict[str, Any]:
        return self.data.get("defaults", {}) or {}

    @property
    def agent_blocks(self) -> dict[str, dict[str, Any]]:
        raw = self.data.get("agent", {}) or {}
        return {str(key): (value or {}) for key, value in raw.items()}

    def get_default_agent(self) -> str | None:
        return _coerce_str(self.defaults.get("agent"))

    def get_default_task(self) -> str | None:
        return _coerce_str(self.defaults.get("task"))

    def get_default_seed(self) -> int | None:
        return _coerce_int(self.defaults.get("seed"))

    def get_agent_block(self, agent: str | None) -> dict[str, Any]:
        if not agent:
            return {}
        return self.agent_blocks.get(agent, {})

    def _get_value(self, key: str, *, agent: str | None = None) -> Any:
        scoped = self.get_agent_block(agent)
        if key in scoped:
            return scoped[key]
        return self.defaults.get(key)

    def get_seed(self, *, agent: str | None = None) -> int | None:
        return _coerce_int(self._get_value("seed", agent=agent))

    def get_task(self, *, agent: str | None = None) -> str | None:
        return _coerce_str(self._get_value("task", agent=agent))


def load_config(path: str | Path | None = None, *, require: bool = False) -> AgentBenchConfig | None:
    explicit = path is not None
    resolved = _resolve_path(path)
    if not resolved:
        if require or explicit:
            suffix = f" {path}" if path else ""
            raise ConfigError(f"Config file{suffix} not found")
        return None
    try:
        data = tomllib.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - TOCTOU guard
        raise ConfigError(f"Config file {resolved} not found") from exc
    except Exception as exc:  # pragma: no cover - toml parsing errors
        raise ConfigError(f"Failed to parse config {resolved}: {exc}") from exc
    return AgentBenchConfig(path=resolved, data=data)


def _resolve_path(path: str | Path | None) -> Path | None:
    if path:
        candidate = Path(path)
        return candidate if candidate.exists() else None
    env_path = _env_override()
    if env_path and env_path.exists():
        return env_path
    for name in DEFAULT_FILENAMES:
        candidate = Path(name)
        if candidate.exists():
            return candidate
    return None


def _env_override() -> Path | None:
    import os

    env_value = os.environ.get(ENV_CONFIG_VAR)
    if not env_value:
        return None
    return Path(env_value)


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None
