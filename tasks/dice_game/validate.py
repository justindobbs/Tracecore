"""Validate dice game task."""


def validate(env):
    """Validate the game outcome."""
    wins = env.get_hidden_state("wins")
    current_roll = env.get_hidden_state("current_roll")
    ok = wins == 1
    if ok:
        return {"ok": True, "message": "Dice game completed successfully"}
    return {"ok": False, "message": f"Wins: {wins}, Rolls: {current_roll}"}
