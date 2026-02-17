"""Actions for dice game task."""

from __future__ import annotations

_ENV = None


def set_env(env):
    global _ENV
    _ENV = env


def roll_dice(result: int) -> dict:
    current_roll = _ENV.get_hidden_state("current_roll")
    max_rolls = _ENV.get_hidden_state("max_rolls")
    target_number = _ENV.get_hidden_state("target_number")
    wins = _ENV.get_hidden_state("wins")

    if current_roll >= max_rolls:
        return {"ok": False, "error": "max_rolls_exceeded"}

    current_roll += 1
    _ENV.set_hidden_state("current_roll", current_roll)

    if result == target_number:
        wins = 1
        _ENV.set_hidden_state("wins", wins)
        _ENV.set_agent_output("result", f"Winner! You rolled {result}")
        return {"ok": True, "message": "winner"}

    _ENV.set_agent_output("result", f"Rolled {result}")
    return {"ok": True, "message": "continue"}


def set_output(key: str, value: str) -> dict:
    _ENV.set_agent_output(key, value)
    return {"ok": True}
