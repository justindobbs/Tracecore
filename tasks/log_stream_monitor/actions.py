"""Actions for the log_stream_monitor task."""

from __future__ import annotations

import json

_ENV = None


def set_env(env) -> None:
    global _ENV
    _ENV = env


def poll_stream(cursor: int) -> dict:
    page_num = cursor + 1
    path = f"/stream/page_{page_num}.json"
    if not _ENV.exists(path):
        return {"ok": True, "entries": [], "next_cursor": cursor, "exhausted": True}
    raw = _ENV.read_file(path)
    page_data = json.loads(raw)
    next_cursor = cursor + 1
    next_path = f"/stream/page_{next_cursor + 1}.json"
    exhausted = not _ENV.exists(next_path)
    return {
        "ok": True,
        "entries": page_data["entries"],
        "next_cursor": next_cursor,
        "exhausted": exhausted,
    }


def set_output(key: str, value: str) -> dict:
    _ENV.set_agent_output(key, value)
    return {"ok": True}
