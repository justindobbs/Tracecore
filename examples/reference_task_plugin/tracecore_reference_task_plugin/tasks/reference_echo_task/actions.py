from __future__ import annotations

_ENV = None


def set_env(env):
    global _ENV
    _ENV = env


def action_schema() -> dict:
    return {
        "actions": [
            {"type": "read_file", "args": {"path": {"type": "string"}}},
            {"type": "set_output", "args": {"key": {"type": "string"}, "value": {"type": "string"}}},
        ]
    }


def execute(action: dict) -> dict:
    if _ENV is None:
        return {"ok": False, "error": "environment_not_initialized"}
    action_type = action.get("type", "")
    args = action.get("args") or {}
    if action_type == "read_file":
        path = args.get("path")
        if not isinstance(path, str) or not path:
            return {"ok": False, "error": "invalid_path"}
        if not _ENV.exists(path):
            return {"ok": False, "error": "file_not_found"}
        return {"ok": True, "content": _ENV.read_file(path)}
    if action_type == "set_output":
        key = args.get("key")
        value = args.get("value")
        if not isinstance(key, str) or not key:
            return {"ok": False, "error": "invalid_key"}
        if not isinstance(value, str):
            return {"ok": False, "error": "invalid_value"}
        _ENV.set_agent_output(key, value)
        return {"ok": True}
    return {"ok": False, "error": f"unknown_action:{action_type}"}
