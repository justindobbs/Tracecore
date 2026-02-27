"""Adversarial agent that tries to exfiltrate hidden state.

Intentionally triggers sandbox protections by reaching into task actions modules
to grab the injected environment and call `get_hidden_state` directly.
"""

from __future__ import annotations

import importlib


class CheaterSimAgent:
    def __init__(self) -> None:
        self.reset({})

    def reset(self, task_spec: dict) -> None:  # pragma: no cover - simple state init
        self.task_spec = task_spec or {}
        self.obs = None

    def observe(self, observation: dict) -> None:
        self.obs = observation

    def _actions_module(self):
        task_id = (self.task_spec or {}).get("id") or ""
        if not task_id:
            return None
        try:
            return importlib.import_module(f"tasks.{task_id}.actions")
        except ModuleNotFoundError:
            return None

    def act(self) -> dict:
        # Attempt to pull the task's injected environment and read hidden state.
        actions_mod = self._actions_module()
        if actions_mod is not None:
            env = getattr(actions_mod, "_ENV", None)
            if env is None and hasattr(actions_mod, "_require_env"):
                try:
                    env = actions_mod._require_env()
                except Exception:
                    env = None
            if env is not None:
                # This call should be blocked by GuardedEnv and surface as a SandboxViolation.
                env.get_hidden_state("SECRET_KEY")

        # If the exploit failed to raise, fall back to an obviously invalid action to end the run.
        return {"type": "unknown_action", "args": {}}


# Alias for loader auto-discovery
Agent = CheaterSimAgent
