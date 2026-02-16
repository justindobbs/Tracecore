"""Actions for the config_drift_remediation task."""

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
    for line in content.splitlines():
        if line.startswith(f"{key}="):
            return {"ok": True, "value": line.split("=", 1)[1]}
    return {"ok": False, "error": "key_not_found"}


def set_output(key: str, value: str) -> dict:
    _ENV.set_agent_output(key, value)
    return {"ok": True}
