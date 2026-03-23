from __future__ import annotations


def setup(seed: int, env):
    token = f"PLUGIN_TOKEN_{seed:04d}"
    env.write_file("/workspace/instructions.txt", "Read the token file and submit the token exactly as written.")
    env.write_file("/workspace/token.txt", token)
    env.set_hidden_state("expected_token", token)
