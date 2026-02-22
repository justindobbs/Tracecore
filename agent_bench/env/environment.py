"""In-memory environment used by the runner."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Iterable

from agent_bench.env.filesystem import normalize_path


class SandboxViolation(RuntimeError):
    """Raised when code outside tasks tries to access guarded state."""


def _normalize_fs_root(path: str) -> str:
    norm = normalize_path(path)
    if norm != "/" and norm.endswith("/"):
        return norm.rstrip("/")
    return norm


class NetworkGuard:
    """Host allowlist matcher for outbound network access."""

    def __init__(self, allowed_hosts: Iterable[str] = ()):
        self._allowed_hosts = tuple(self._normalize_host(host) for host in allowed_hosts if host)

    @staticmethod
    def _normalize_host(host: str) -> str:
        normalized = host.strip().lower().rstrip(".")
        if normalized.startswith("[") and normalized.endswith("]"):
            normalized = normalized[1:-1]
        return normalized

    @staticmethod
    def _extract_host(host: str) -> tuple[str, str | None, int | None]:
        raw = host.strip()
        scheme = None
        if "://" in raw:
            # Avoid urlparse dependency; split scheme and keep netloc.
            scheme, raw = raw.split("://", 1)
            scheme = scheme.strip().lower()
        raw = raw.split("/", 1)[0]
        port = None
        if raw.startswith("[") and "]" in raw:
            bracketed, remainder = raw.split("]", 1)
            raw = bracketed.lstrip("[")
            if remainder.startswith(":"):
                remainder = remainder[1:]
                if remainder.isdigit():
                    port = int(remainder)
        elif ":" in raw:
            raw, raw_port = raw.rsplit(":", 1)
            if raw_port.isdigit():
                port = int(raw_port)
        return raw.strip().lower().rstrip("."), scheme, port

    @staticmethod
    def _match(entry: str, host: str) -> bool:
        if entry == "*":
            return True
        if entry.startswith("*."):
            suffix = entry[1:]
            return host.endswith(suffix) and host != suffix.lstrip(".")
        return host == entry

    def allowed(self, host: str) -> bool:
        if not self._allowed_hosts:
            return False
        normalized, _, _ = self._extract_host(host)
        if not normalized:
            return False
        return any(self._match(entry, normalized) for entry in self._allowed_hosts)

    def inspect(self, host: str) -> tuple[str, str | None, int | None]:
        normalized, scheme, port = self._extract_host(host)
        if scheme and scheme not in ("http", "https"):
            raise SandboxViolation(f"sandbox_violation: network scheme denied: {scheme}")
        if port is not None and port not in (80, 443):
            raise SandboxViolation(f"sandbox_violation: network port denied: {port}")
        return normalized, scheme, port

    def check(self, host: str) -> str:
        normalized, _, _ = self.inspect(host)
        if not self.allowed(host):
            raise SandboxViolation(f"sandbox_violation: network access denied: {host}")
        return normalized


class GuardedEnv:
    """Thin proxy that only allows access from task modules."""


    def __init__(
        self,
        env: "Environment",
        allowed_prefixes: tuple[str, ...] = ("tasks.", "agent_bench.tasks."),
        filesystem_roots: Iterable[str] = (),
        network_hosts: Iterable[str] = (),
        allow_test_callers: bool = False,
    ):
        self._env = env
        self._allowed_prefixes = allowed_prefixes
        self._filesystem_roots = tuple(_normalize_fs_root(root) for root in filesystem_roots)
        self._network_guard = NetworkGuard(network_hosts)
        self._allow_test_callers = allow_test_callers
        self._audit_entries: list[dict] = []
        self._audit_step: int | None = None


    def _ensure_allowed(self) -> None:
        if self._allow_test_callers:
            return
        for frame_info in inspect.stack()[1:]:
            mod = frame_info.frame.f_globals.get("__name__", "")
            filename = frame_info.filename.replace("\\", "/")
            if any(mod.startswith(prefix) for prefix in self._allowed_prefixes) or \
               "/tasks/" in filename:
                return
        raise SandboxViolation("sandbox_violation: forbidden access to environment state")


    def _ensure_fs_allowed(self, path: str) -> str:
        try:
            norm = normalize_path(path)
        except ValueError as exc:
            raise SandboxViolation(f"sandbox_violation: invalid path: {path}") from exc
        if not self._filesystem_roots:
            raise SandboxViolation(
                f"sandbox_violation: filesystem access denied: {norm} (allowed_roots=[])"
            )
        for root in self._filesystem_roots:
            if root == "/" or norm == root or norm.startswith(root + "/"):
                return norm
        raise SandboxViolation(
            f"sandbox_violation: filesystem access denied: {norm} "
            f"(allowed_roots={list(self._filesystem_roots)})"
        )

    def _record_audit(self, entry: dict) -> None:
        if self._audit_step is None:
            return
        self._audit_entries.append(entry)

    def begin_step(self, step: int) -> None:
        self._audit_step = step
        self._audit_entries = []

    def consume_audit(self) -> list[dict]:
        entries = list(self._audit_entries)
        self._audit_entries = []
        self._audit_step = None
        return entries

    # File surface
    def list_dir(self, path: str) -> list[str]:
        self._ensure_allowed()
        norm = self._ensure_fs_allowed(path)
        self._record_audit({"type": "fs", "op": "list_dir", "path": norm})
        return self._env.list_dir(path)


    def read_file(self, path: str) -> str:
        self._ensure_allowed()
        norm = self._ensure_fs_allowed(path)
        self._record_audit({"type": "fs", "op": "read_file", "path": norm})
        return self._env.read_file(path)

    def exists(self, path: str) -> bool:
        self._ensure_allowed()
        norm = self._ensure_fs_allowed(path)
        self._record_audit({"type": "fs", "op": "exists", "path": norm})
        return self._env.exists(path)

    def write_file(self, path: str, content: str) -> None:
        self._ensure_allowed()
        norm = self._ensure_fs_allowed(path)
        self._record_audit({"type": "fs", "op": "write_file", "path": norm})
        return self._env.write_file(path, content)

    # Network surface
    def require_network(self, host: str) -> None:
        self._ensure_allowed()
        normalized = self._network_guard.check(host)
        self._record_audit({"type": "net", "host": normalized})

    def network_guard(self) -> NetworkGuard:
        return self._network_guard

    # Hidden state
    def set_hidden_state(self, key: str, value: object) -> None:
        self._ensure_allowed()
        return self._env.set_hidden_state(key, value)

    def get_hidden_state(self, key: str, default: object | None = None) -> object | None:
        self._ensure_allowed()
        return self._env.get_hidden_state(key, default)

    # Output surface
    def set_agent_output(self, key: str, value: str) -> None:
        self._ensure_allowed()
        return self._env.set_agent_output(key, value)

    def get_agent_output(self, key: str, default: str | None = None) -> str | None:
        self._ensure_allowed()
        return self._env.get_agent_output(key, default)

    # Observability helpers
    def mark_seen(self, paths: list[str]) -> None:
        self._ensure_allowed()
        return self._env.mark_seen(paths)

    def visible_state(self) -> dict:
        self._ensure_allowed()
        return self._env.visible_state()


@dataclass
class Environment:
    files: dict[str, str] = field(default_factory=dict)
    hidden_state: dict[str, object] = field(default_factory=dict)
    agent_output: dict[str, str] = field(default_factory=dict)
    seen_paths: set[str] = field(default_factory=set)

    def write_file(self, path: str, content: str) -> None:
        norm = normalize_path(path)
        self.files[norm] = content

    def read_file(self, path: str) -> str:
        norm = normalize_path(path)
        return self.files[norm]

    def exists(self, path: str) -> bool:
        norm = normalize_path(path)
        return norm in self.files

    def list_dir(self, path: str) -> list[str]:
        norm = normalize_path(path)
        prefix = norm.rstrip("/") + "/"
        seen = set()
        for file_path in self.files.keys():
            if not file_path.startswith(prefix):
                continue
            rest = file_path[len(prefix):]
            part = rest.split("/", 1)[0]
            seen.add(prefix + part if part else prefix)
        return sorted(seen)

    def mark_seen(self, paths: list[str]) -> None:
        for p in paths:
            self.seen_paths.add(normalize_path(p))

    def set_hidden_state(self, key: str, value: object) -> None:
        self.hidden_state[key] = value

    def get_hidden_state(self, key: str, default: object | None = None) -> object | None:
        return self.hidden_state.get(key, default)

    def set_agent_output(self, key: str, value: str) -> None:
        self.agent_output[key] = value

    def get_agent_output(self, key: str, default: str | None = None) -> str | None:
        return self.agent_output.get(key, default)

    def visible_state(self) -> dict:
        return {"files_seen": sorted(self.seen_paths)}
