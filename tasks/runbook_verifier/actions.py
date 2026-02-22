"""Actions for the runbook_verifier task."""

from __future__ import annotations

from tasks.runbook_verifier.shared import TARGET_KEY

_ENV = None


def set_env(env) -> None:
    global _ENV
    _ENV = env


def _require_env():
    if _ENV is None:
        raise RuntimeError("Environment not initialized. Did you call set_env()?")
    return _ENV


def list_dir(path: str) -> dict:
    env = _require_env()
    files = env.list_dir(path)
    return {"ok": True, "files": files}


def read_file(path: str) -> dict:
    env = _require_env()
    if not env.exists(path):
        return {"ok": False, "error": "file_not_found"}
    return {"ok": True, "content": env.read_file(path)}


def extract_value(content: str, key: str) -> dict:
    for line in content.splitlines():
        if line.startswith(f"{key}="):
            return {"ok": True, "value": line.split("=", 1)[1]}
    return {"ok": False, "error": "key_not_found"}


def set_output(key: str, value: str) -> dict:
    env = _require_env()
    if key != TARGET_KEY:
        return {"ok": False, "error": "invalid_output_key"}
    env.set_agent_output(key, value)
    return {"ok": True}
