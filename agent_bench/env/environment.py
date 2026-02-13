"""In-memory environment used by the runner."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_bench.env.filesystem import normalize_path


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