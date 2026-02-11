"""Environment initialization for the rate_limited_api task."""

from __future__ import annotations

from random import Random

from tasks.rate_limited_api.service import MockRateLimitedAPI
from tasks.rate_limited_api.shared import OUTPUT_KEY, PAYLOAD_KEY, SECRET_KEY, SERVICE_KEY


def setup(seed: int, env) -> None:
    rng = Random(seed)

    secret = f"ACCESS-{rng.randint(100000, 999999)}"
    nonce = f"{rng.randint(1000, 9999)}"
    required_payload = {
        "client_id": "openclaw_agent",
        "nonce": nonce,
    }

    service = MockRateLimitedAPI(secret=secret, required_payload=required_payload, blocked_until=2)

    env.set_hidden_state(SERVICE_KEY, service)
    env.set_hidden_state(PAYLOAD_KEY, required_payload)
    env.set_hidden_state(SECRET_KEY, secret)

    instructions = (
        "# Rate-limited API Task\n"
        "The ACCESS_TOKEN is only available via the /token endpoint.\n\n"
        "## How to interact\n"
        "- Use the `call_api` action with payload JSON.\n"
        "- The payload must include: client_id=openclaw_agent, nonce=%s.\n"
        "- The API enforces a strict rate limit. Respect `retry_after` hints before retrying.\n"
        "- Temporary failures can be retried immediately.\n"
        "- Use `wait` to advance simulated time in steps.\n"
        f"- When you retrieve the token, store it via `set_output` using key {OUTPUT_KEY}.\n"
    ) % nonce

    readme_path = "/app/README.md"
    env.write_file(readme_path, instructions)
    env.mark_seen([readme_path])
