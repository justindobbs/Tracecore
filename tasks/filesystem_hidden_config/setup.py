"""Task setup for filesystem_hidden_config."""

from random import Random


def setup(seed: int, env):
    rng = Random(seed)

    # Public files
    env.write_file("/app/readme.txt", "Welcome to the app.")
    env.write_file("/app/config.example", "API_KEY=changeme")

    # Hidden real config
    suffix = rng.randint(1000, 9999)
    hidden_path = f"/app/.config_{suffix}"

    env.write_file(hidden_path, "API_KEY=correct_value")

    # Ground truth for validator only
    env.set_hidden_state("config_path", hidden_path)
