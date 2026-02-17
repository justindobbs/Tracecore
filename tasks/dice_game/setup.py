"""Setup dice game task."""


def setup(seed, env):
    """Set up the dice game environment."""
    target_number = 4
    max_rolls = 3

    env.set_hidden_state("target_number", target_number)
    env.set_hidden_state("max_rolls", max_rolls)
    env.set_hidden_state("current_roll", 0)
    env.set_hidden_state("wins", 0)

    return {
        "game_state": {
            "target_number": target_number,
            "max_rolls": max_rolls,
            "current_roll": 0,
            "wins": 0,
        }
    }
