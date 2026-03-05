"""Automation helpers for running TraceCore checks and suggesting guarded fixes."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str


def _run(argv: list[str], *, cwd: Path) -> CommandResult:
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        shell=False,
    )
    return CommandResult(
        argv=argv,
        cwd=str(cwd),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def run_pytest(*, cwd: Path, args: list[str] | None = None) -> CommandResult:
    argv = [sys.executable, "-m", "pytest"]
    if args:
        argv.extend(args)
    return _run(argv, cwd=cwd)


def run_agent_bench_tasks_validate(*, cwd: Path, include_registry: bool = True) -> CommandResult:
    argv = [sys.executable, "-m", "agent_bench.cli", "tasks", "validate"]
    if include_registry:
        argv.append("--registry")
    return _run(argv, cwd=cwd)


_FIX_PYDANTIC_AGENT_IMPORT = re.compile(r"^from\s+pydantic_ai\s+import\s+Agent\s*(,\s*RunContext\s*)?$", re.M)


def suggest_fix_pydantic_agent_import(source: str) -> tuple[bool, str]:
    """Avoid agent loader picking up pydantic_ai.Agent by accident.

    The loader prefers a module attribute named `Agent`. If an agent file imports
    `pydantic_ai.Agent` at module scope, the loader may return the wrong class,
    leading to runtime errors like "Agent has no attribute reset".

    This fixer rewrites `from pydantic_ai import Agent` to `from pydantic_ai import Agent as PydanticAgent`.
    """

    if "from pydantic_ai import Agent" not in source:
        return False, source

    lines = source.splitlines(keepends=True)
    changed = False
    out: list[str] = []

    for line in lines:
        if line.startswith("from pydantic_ai import ") and "Agent" in line:
            if "Agent as PydanticAgent" in line:
                out.append(line)
                continue
            if "Agent, RunContext" in line:
                out.append(line.replace("Agent, RunContext", "Agent as PydanticAgent, RunContext"))
                changed = True
                continue
            if line.strip() == "from pydantic_ai import Agent":
                out.append("from pydantic_ai import Agent as PydanticAgent\n")
                changed = True
                continue
        out.append(line)

    if not changed:
        return False, source
    return True, "".join(out)


def apply_fix(path: Path, *, dry_run: bool = True) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    changed, updated = suggest_fix_pydantic_agent_import(source)
    if not changed:
        return {"path": str(path), "changed": False}

    if not dry_run:
        path.write_text(updated, encoding="utf-8")

    return {
        "path": str(path),
        "changed": True,
        "dry_run": dry_run,
    }


def maintain(
    *,
    cwd: Path,
    pytest_args: list[str] | None = None,
    validate_tasks: bool = True,
    fix_agent_files: list[str] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    results: dict[str, Any] = {"cwd": str(cwd)}

    if validate_tasks:
        task_res = run_agent_bench_tasks_validate(cwd=cwd, include_registry=True)
        results["tasks_validate"] = {
            "argv": task_res.argv,
            "returncode": task_res.returncode,
            "stdout": task_res.stdout,
            "stderr": task_res.stderr,
        }

    pytest_res = run_pytest(cwd=cwd, args=pytest_args)
    results["pytest"] = {
        "argv": pytest_res.argv,
        "returncode": pytest_res.returncode,
        "stdout": pytest_res.stdout,
        "stderr": pytest_res.stderr,
    }

    fixes: list[dict[str, Any]] = []
    if fix_agent_files:
        for raw in fix_agent_files:
            path = (cwd / raw).resolve() if not Path(raw).is_absolute() else Path(raw)
            if path.exists():
                fixes.append(apply_fix(path, dry_run=dry_run))
            else:
                fixes.append({"path": str(path), "changed": False, "error": "not_found"})
    results["fixes"] = fixes

    fix_errors = sum(1 for fix in fixes if fix.get("error"))
    results["fix_errors"] = fix_errors

    ok = True
    if validate_tasks and results.get("tasks_validate", {}).get("returncode") not in (0, None):
        ok = False
    if results.get("pytest", {}).get("returncode") not in (0, None):
        ok = False
    if fix_errors:
        ok = False

    results["ok"] = ok
    return results


def dumps_summary(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)
