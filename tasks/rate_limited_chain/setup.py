"""Environment initialization for the rate_limited_chain task."""

from __future__ import annotations

from random import Random

from tasks.rate_limited_chain.service import MockChainAPI
from tasks.rate_limited_chain.shared import (
    HANDSHAKE_TEMPLATE_KEY,
    OUTPUT_KEY,
    PAYLOAD_KEY,
    README_PATH,
    SECRET_KEY,
    SERVICE_KEY,
)


def setup(seed: int, env) -> None:
    rng = Random(seed)

    secret = f"ACCESS-{rng.randint(100000, 999999)}"
    chain_code = f"CHAIN{rng.randint(1000, 9999)}"
    nonce = f"{rng.randint(1000, 9999)}"
    required_payload = {
        "client_id": "agent_bench_chain",
        "nonce": nonce,
    }

    service = MockChainAPI(
        secret=secret,
        required_payload=required_payload,
        chain_code=chain_code,
        blocked_until=3,
    )

    template = (
        "To finalize the handshake, respond with: CHAIN-<handshake_id>-%s.\n"
        "Handshakes expire quickly—request a new one if you miss the window."
    ) % chain_code

    env.set_hidden_state(SERVICE_KEY, service)
    env.set_hidden_state(PAYLOAD_KEY, required_payload)
    env.set_hidden_state(SECRET_KEY, secret)
    env.set_hidden_state(HANDSHAKE_TEMPLATE_KEY, template)

    instructions = (
        "# Rate-limited Chain Task\n"
        "This API requires a successful /handshake -> /handshake_commit flow before /token.\n\n"
        "1. Call `call_api` on `/handshake` to get a handshake_id.\n"
        "2. Combine the ID with the template phrase in README to call `/handshake_commit`.\n"
        "3. Only after confirmation may you call `/token` with the required payload.\n"
        "4. Respect rate limits using `inspect_status` + `wait`.\n"
        f"5. When you get the token, store it via `set_output` using key {OUTPUT_KEY}.\n"
    )

    env.write_file(README_PATH, instructions)
    env.mark_seen([README_PATH])
    env.set_hidden_state("chain_task_initialized", True)
*** End of File
