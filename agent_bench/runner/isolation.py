"""Episode isolation utilities.

Provides helpers for running a single episode inside a clean child process
so that task state, module-level globals, and environment variables cannot
leak between episodes in a batch run.

The primary public API is ``run_isolated``, which mirrors
``agent_bench.runner.runner.run`` but executes in a subprocess.
"""

from __future__ import annotations

import multiprocessing
import queue
import sys
from pathlib import Path
from typing import Any


def _worker(agent: str, task_ref: str, seed: int, result_q: "multiprocessing.Queue[Any]") -> None:
    """Child process entry point — imports runner fresh and sends result back."""
    try:
        repo_root = str(Path(__file__).parent.parent.parent.resolve())
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from agent_bench.runner.runner import run  # noqa: PLC0415
        result = run(agent, task_ref, seed)
        result_q.put({"ok": True, "result": result})
    except Exception as exc:  # noqa: BLE001
        result_q.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def run_isolated(agent: str, task_ref: str, seed: int = 0, *, timeout: int | None = None) -> dict:
    """Run a single episode in an isolated child process.

    Parameters
    ----------
    agent:
        Path to the agent module.
    task_ref:
        Task reference string in ``<id>@<version>`` format.
    seed:
        Deterministic seed.
    timeout:
        Wall-clock timeout in seconds.  Raises ``TimeoutError`` if exceeded.

    Returns
    -------
    dict
        The run artifact dict as returned by ``runner.run``.

    Raises
    ------
    TimeoutError
        If *timeout* is set and the episode exceeds it.
    RuntimeError
        If the child process raises an unexpected exception.
    """
    ctx = multiprocessing.get_context("spawn")
    result_q: multiprocessing.Queue[Any] = ctx.Queue()
    proc = ctx.Process(target=_worker, args=(agent, task_ref, seed, result_q), daemon=True)
    proc.start()
    try:
        raw = result_q.get(timeout=timeout)
    except queue.Empty:
        proc.kill()
        proc.join(timeout=5)
        raise TimeoutError(
            f"isolated run timed out after {timeout}s "
            f"(agent={agent}, task_ref={task_ref}, seed={seed})"
        )
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join(timeout=5)

    if not raw.get("ok"):
        raise RuntimeError(raw.get("error", "unknown error in isolated worker"))

    return raw["result"]


def enforce_isolation() -> None:
    """No-op compatibility shim kept for any callers that import this symbol."""
    return None
