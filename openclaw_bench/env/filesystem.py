"""Filesystem helpers."""

from __future__ import annotations

from pathlib import PurePosixPath


def normalize_path(path: str) -> str:
    if not path:
        raise ValueError("path must be non-empty")
    p = PurePosixPath(path)
    norm = p.as_posix()
    if not norm.startswith("/"):
        norm = "/" + norm
    if "/../" in f"{norm}/" or norm.endswith("/.."):
        raise ValueError("parent traversal is not allowed")
    return norm
