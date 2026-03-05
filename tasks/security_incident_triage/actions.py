"""Actions for the security_incident_triage task."""

from __future__ import annotations

_ENV = None


def set_env(env) -> None:
    global _ENV
    _ENV = env


def _require_env():
    if _ENV is None:  # pragma: no cover - defensive guard
        raise RuntimeError("environment not set; call set_env first")


def list_dir(path: str) -> dict:
    _require_env()
    files = _ENV.list_dir(path)
    return {"ok": True, "files": files}


def read_file(path: str) -> dict:
    _require_env()
    if not _ENV.exists(path):
        return {"ok": False, "error": "file_not_found"}
    return {"ok": True, "content": _ENV.read_file(path)}


def extract_value(content: str, key: str) -> dict:
    for line in content.splitlines():
        if line.startswith(f"{key}="):
            return {"ok": True, "value": line.split("=", 1)[1]}
    return {"ok": False, "error": "key_not_found"}


def find_line(path: str, needle: str) -> dict:
    file_result = read_file(path)
    if not file_result["ok"]:
        return file_result
    for line in file_result["content"].splitlines():
        if needle in line:
            return {"ok": True, "line": line}
    return {"ok": False, "error": "line_not_found"}


def set_output(key: str, value: str) -> dict:
    _require_env()
    _ENV.set_agent_output(key, value)
    return {"ok": True}
