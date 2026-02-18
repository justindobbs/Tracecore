"""Environment initialization for the log_stream_monitor task."""

from __future__ import annotations

import json
from random import Random

STREAM_CODE_KEY = "STREAM_CODE"
EXPECTED_KEY = "expected_stream_code"

NOISE_TEMPLATES = [
    "INFO boot sequence started",
    "INFO health check passed",
    "WARN queue depth {n} approaching threshold",
    "INFO telemetry upload complete",
    "ERROR transient timeout on replica {n} (non-critical)",
    "WARN retry window extended to {n}s",
    "INFO cache warmed successfully",
    "ERROR connection reset by peer (transient)",
]


def _noise_entry(rng: Random) -> str:
    template = rng.choice(NOISE_TEMPLATES)
    return template.format(n=rng.randint(1, 99))


def setup(seed: int, env) -> None:
    rng = Random(seed)

    stream_code = f"SC-{rng.randint(100, 999)}"
    num_pages = rng.randint(4, 6)
    critical_page = rng.randint(1, num_pages)

    for page_num in range(1, num_pages + 1):
        entries = []
        noise_count = rng.randint(2, 4)
        for _ in range(noise_count):
            entries.append(_noise_entry(rng))
        if page_num == critical_page:
            entries.insert(
                rng.randint(0, len(entries)),
                f"CRITICAL ingest_failure {STREAM_CODE_KEY}={stream_code}",
            )
        page_data = {"page": page_num, "entries": entries}
        env.write_file(f"/stream/page_{page_num}.json", json.dumps(page_data))

    env.set_hidden_state(EXPECTED_KEY, stream_code)
    env.set_hidden_state("num_pages", num_pages)
    env.mark_seen([])
