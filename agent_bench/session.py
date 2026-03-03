from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agent_bench.runner.runlog import RUN_LOG_ROOT


SESSION_PATH = Path(".agent_bench") / "session.json"


@dataclass(frozen=True)
class SessionPointer:
    latest_run_id: str | None = None
    latest_success_run_id: str | None = None
    latest_bundle_dir: str | None = None
    agent: str | None = None
    task_ref: str | None = None
    seed: int | None = None
    updated_at: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_session(path: Path = SESSION_PATH) -> SessionPointer | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return SessionPointer(
        latest_run_id=payload.get("latest_run_id"),
        latest_success_run_id=payload.get("latest_success_run_id"),
        latest_bundle_dir=payload.get("latest_bundle_dir"),
        agent=payload.get("agent"),
        task_ref=payload.get("task_ref"),
        seed=payload.get("seed"),
        updated_at=payload.get("updated_at"),
    )


def save_session(pointer: SessionPointer, path: Path = SESSION_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "latest_run_id": pointer.latest_run_id,
        "latest_success_run_id": pointer.latest_success_run_id,
        "latest_bundle_dir": pointer.latest_bundle_dir,
        "agent": pointer.agent,
        "task_ref": pointer.task_ref,
        "seed": pointer.seed,
        "updated_at": pointer.updated_at or _utc_now_iso(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def update_after_run(*, result: dict) -> SessionPointer:
    run_id = result.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run result missing run_id")

    agent = result.get("agent")
    task_ref = result.get("task_ref")
    seed = result.get("seed")
    success = bool(result.get("failure_type") is None)

    existing = load_session() or SessionPointer()
    latest_success = existing.latest_success_run_id
    if success:
        latest_success = run_id

    updated = SessionPointer(
        latest_run_id=run_id,
        latest_success_run_id=latest_success,
        latest_bundle_dir=existing.latest_bundle_dir,
        agent=agent if isinstance(agent, str) else existing.agent,
        task_ref=task_ref if isinstance(task_ref, str) else existing.task_ref,
        seed=seed if isinstance(seed, int) else existing.seed,
        updated_at=_utc_now_iso(),
    )
    save_session(updated)
    return updated


def update_after_bundle(*, bundle_dir: Path) -> SessionPointer:
    existing = load_session() or SessionPointer()
    updated = SessionPointer(
        latest_run_id=existing.latest_run_id,
        latest_success_run_id=existing.latest_success_run_id,
        latest_bundle_dir=str(bundle_dir),
        agent=existing.agent,
        task_ref=existing.task_ref,
        seed=existing.seed,
        updated_at=_utc_now_iso(),
    )
    save_session(updated)
    return updated


def latest_run_id(*, prefer_success: bool = False) -> str | None:
    session = load_session()
    if session is None:
        return None
    if prefer_success and session.latest_success_run_id:
        return session.latest_success_run_id
    return session.latest_run_id


def latest_run_path(*, prefer_success: bool = False) -> Path | None:
    run_id = latest_run_id(prefer_success=prefer_success)
    if not run_id:
        return None
    return RUN_LOG_ROOT / f"{run_id}.json"
