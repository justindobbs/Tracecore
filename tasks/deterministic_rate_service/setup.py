"""Environment setup for deterministic rate service task."""

from __future__ import annotations

from random import Random

from tasks.deterministic_rate_service.service import MockDeterministicService
from tasks.deterministic_rate_service.shared import (
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
    nonce = f"{rng.randint(1000, 9999)}"
    client_id = "agent_bench_drs"
    payload = {"client_id": client_id, "nonce": nonce}

    chain_code = f"DRS{rng.randint(1000, 9999)}"
    template = (
        "Deterministic Rate Service\n"
        "To confirm the session, respond with: DRS-<handshake_id>-%s.\n"
        "Respect retry windows: wait the specified steps after rate_limited errors.\n"
        "Temporary failures should be retried immediately without waiting."
    ) % chain_code

    service = MockDeterministicService(
        secret=secret,
        required_payload=payload,
        handshake_phrase="DRS-<handshake_id>-%s" % chain_code,
        blocked_until=2,
        transient_once=True,
    )

    instructions = (
        "# Deterministic Rate Service\n"
        "This API enforces a strict sequence. To succeed:\n\n"
        "1. Use `call_api` on `/handshake` to obtain `handshake_id`.\n"
        "2. Fetch the template via `get_handshake_template` and commit using `/handshake_commit`.\n"
        "3. Only after confirmation call `/token` with the required payload (client_id + nonce + handshake_id).\n"
        "4. If you receive `rate_limited`, call `wait` for the provided `retry_after` steps before retrying.\n"
        "5. If you receive `temporary_failure`, retry `/token` immediately.\n"
        "6. Any `bad_request` or `invalid_handshake` means you must restart the handshake.\n"
        f"7. When you get the ACCESS_TOKEN, store it via `set_output` using key {OUTPUT_KEY}.\n"
    )

    env.set_hidden_state(SERVICE_KEY, service)
    env.set_hidden_state(PAYLOAD_KEY, payload)
    env.set_hidden_state(SECRET_KEY, secret)
    env.set_hidden_state(HANDSHAKE_TEMPLATE_KEY, template)
    env.write_file(README_PATH, instructions)
    env.mark_seen([README_PATH])
