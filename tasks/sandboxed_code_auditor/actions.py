"""Actions for the sandboxed_code_auditor task."""

from __future__ import annotations

_ENV = None


def set_env(env) -> None:
    global _ENV
    _ENV = env


def list_dir(path: str) -> dict:
    files = _ENV.list_dir(path)
    return {"ok": True, "files": files}


def read_file(path: str) -> dict:
    if not _ENV.exists(path):
        return {"ok": False, "error": "file_not_found"}
    return {"ok": True, "content": _ENV.read_file(path)}


def extract_value(content: str, key: str) -> dict:
    token = f"{key}="
    for line in content.splitlines():
        candidate = line.strip()
        if candidate.startswith("#"):
            candidate = candidate.lstrip("# ")
        if token in candidate:
            _, value = candidate.split(token, 1)
            return {"ok": True, "value": value.strip()}
    return {"ok": False, "error": "key_not_found"}


def set_output(key: str, value: str) -> dict:
    _ENV.set_agent_output(key, value)
    return {"ok": True}
