from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_bench.runner.bundle import verify_bundle

LEADERBOARD_ROOT = Path("deliverables") / "leaderboard"
SUBMISSIONS_DIRNAME = "submissions"
INDEX_FILENAME = "index.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_str(payload: dict[str, Any], key: str, *, source: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source} missing required field: {key}")
    return value


def build_submission_record(bundle_dir: Path) -> dict[str, Any]:
    bundle_dir = Path(bundle_dir)
    verify_report = verify_bundle(bundle_dir)
    if not verify_report.get("ok"):
        raise ValueError("bundle verification failed")

    manifest_path = bundle_dir / "manifest.json"
    signature_path = bundle_dir / "signature.json"
    validator_path = bundle_dir / "validator.json"
    if not manifest_path.exists():
        raise ValueError("bundle missing manifest.json")
    if not validator_path.exists():
        raise ValueError("bundle missing validator.json")
    if not signature_path.exists():
        raise ValueError("bundle must be signed before leaderboard ingestion")

    manifest = _load_json(manifest_path)
    signature = _load_json(signature_path)
    validator = _load_json(validator_path)

    run_id = _require_str(manifest, "run_id", source="manifest")
    trace_id = _require_str(manifest, "trace_id", source="manifest")
    agent = _require_str(manifest, "agent", source="manifest")
    task_ref = _require_str(manifest, "task_ref", source="manifest")
    signature_algorithm = _require_str(signature, "algorithm", source="signature")
    bundle_signature = _require_str(signature, "signature_hex", source="signature")

    public_key_pem = signature.get("public_key_pem")
    if not isinstance(public_key_pem, str) or not public_key_pem.strip():
        raise ValueError("signature missing required field: public_key_pem")

    submission = {
        "submission_id": f"{run_id}:{task_ref}",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "bundle_dir": str(bundle_dir.resolve()),
        "run": {
            "run_id": run_id,
            "trace_id": trace_id,
            "agent": agent,
            "task_ref": task_ref,
            "task_id": manifest.get("task_id"),
            "version": manifest.get("version"),
            "seed": manifest.get("seed"),
            "harness_version": manifest.get("harness_version"),
            "started_at": manifest.get("started_at"),
            "completed_at": manifest.get("completed_at"),
            "success": manifest.get("success"),
            "termination_reason": manifest.get("termination_reason"),
            "failure_type": manifest.get("failure_type"),
            "failure_reason": manifest.get("failure_reason"),
            "steps_used": manifest.get("steps_used"),
            "tool_calls_used": manifest.get("tool_calls_used"),
            "trace_entry_count": manifest.get("trace_entry_count"),
            "sandbox": manifest.get("sandbox"),
        },
        "validator": validator,
        "provenance": {
            "signature_algorithm": signature_algorithm,
            "bundle_signature": bundle_signature,
            "signing_public_key_pem": public_key_pem,
            "signed_file": signature.get("signed_file"),
        },
        "verify_report": verify_report,
    }
    return submission


def ingest_bundle(bundle_dir: Path, *, dest_root: Path | None = None) -> dict[str, Any]:
    submission = build_submission_record(bundle_dir)
    root = Path(dest_root) if dest_root is not None else LEADERBOARD_ROOT
    submissions_dir = root / SUBMISSIONS_DIRNAME
    submissions_dir.mkdir(parents=True, exist_ok=True)

    submission_path = submissions_dir / f"{submission['run']['run_id']}.json"
    submission_path.write_text(json.dumps(submission, ensure_ascii=False, indent=2), encoding="utf-8")

    index_path = root / INDEX_FILENAME
    if index_path.exists():
        index_payload = _load_json(index_path)
    else:
        index_payload = {"version": 1, "generated_at": None, "submissions": []}

    submissions = index_payload.get("submissions")
    if not isinstance(submissions, list):
        submissions = []

    entry = {
        "submission_id": submission["submission_id"],
        "run_id": submission["run"]["run_id"],
        "agent": submission["run"]["agent"],
        "task_ref": submission["run"]["task_ref"],
        "success": submission["run"].get("success"),
        "ingested_at": submission["ingested_at"],
        "submission_file": str(submission_path.resolve()),
    }
    submissions = [item for item in submissions if item.get("run_id") != submission["run"]["run_id"]]
    submissions.append(entry)
    submissions.sort(key=lambda item: (item.get("ingested_at") or "", item.get("run_id") or ""))

    index_payload["version"] = 1
    index_payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    index_payload["submissions"] = submissions
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "submission": submission,
        "submission_file": str(submission_path.resolve()),
        "index_file": str(index_path.resolve()),
    }


__all__ = [
    "LEADERBOARD_ROOT",
    "INDEX_FILENAME",
    "SUBMISSIONS_DIRNAME",
    "build_submission_record",
    "ingest_bundle",
]
