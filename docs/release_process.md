# Release Process

This document describes the standard checklist for cutting a TraceCore release. Follow these steps in order for every version bump.

## Release checklist

1. **Finalize changelog** — Move all `## [Unreleased]` entries into a new `## [X.Y.Z] - YYYY-MM-DD` section in `CHANGELOG.md`. Leave empty `[Unreleased]` placeholders for the next cycle. If any changes touched the CLI contracts, artifact schema, or bundle layout, ensure `docs/contract.md` and `CHANGELOG.md` describe them explicitly.

2. **Verify behavior** — Complete every step in [`docs/manual_verification.md`](manual_verification.md) and record the resulting `run_id` values. These become the reproducible proof of behavior for the release.

3. **Stamp versions** — Update the runtime/package version string in:
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `agent_bench/webui/app.py` → `version="X.Y.Z"` in the `FastAPI(...)` constructor

   Then run a task and confirm the artifact reports `"harness_version": "X.Y.Z"`. Spec versions remain independent; only update `/spec/tracecore-spec-*.md` when the normative contracts change.

4. **Run tests** — `python -m pytest` — all tests must pass.

5. **Validate tasks** — `agent-bench tasks validate --registry` — must exit 0.

6. **Update SPEC_FREEZE.md** — Confirm the header version and task table reflect the release. Add any new frozen tasks; mark any newly internal tasks in the experimental section. If the spec itself changed, update `/spec/tracecore-spec-*.md`, `/spec/artifact-schema-*.json`, `/spec/compliance-checklist-*.md`, and `/spec/determinism.md` together and document the new spec version.

7. **Produce trust evidence bundle** — Per `SPEC_FREEZE.md` rule 4, create `deliverables/trust_bundle_vX.Y.Z/` containing:
   - `metadata.json` (harness version, git SHA, task list, seed policy)
   - Representative run artifacts referenced in release notes
   - Baseline exports used for gating

8. **Contract acknowledgement** — Reread `docs/contract.md` and confirm the release either (a) leaves the spec untouched, or (b) includes the required major/minor bump and `/spec/` updates per the "Breaking Change Procedure" section. Record the runtime version + implemented spec version in the release PR description.

9. **Tag & push**:
   ```sh
   git tag -a vX.Y.Z -m "TraceCore vX.Y.Z"
   git push origin vX.Y.Z
   ```

---

## Historical release notes

### v0.1.0 — 2026-01-15
Initial public release with filesystem and rate-limited API tasks, baseline FastAPI UI, and reference agents.

### v0.2.0 — 2026-02-14
Structured failure taxonomy, CLI `--failure-type` filter, Web UI failure labels, OpenClaw quickstart tutorial.

### v0.3.0 — 2026-02-15
Task manifest schema v0.1 (`task.toml`), determinism regression tests, baseline compare enhancements, `agent-bench.toml` config, GitHub Actions reusable workflow.

### v0.4.1 — 2026-02-16
Operations suite tasks (`log_alert_triage@1`, `config_drift_remediation@1`, `incident_recovery_chain@1`), `OpsTriageAgent`, task contract spec, CLI task validation, terminal `logic_failure` runner support, TraceCore brand docs.

### v0.5.0 — 2026-02-18
Public release hardening: CLI/doc correctness fixes, `scripts/policy_gate.py`, `CONTRIBUTING.md`, `SECURITY.md`, `dice_game` marked internal, `record_mode.md` future-vision banner, `non_termination` clarified as reserved, CHANGELOG ordering fixed, `pydantic-ai` version bounded.

### v0.6.0 — 2026-02-19
OpenClaw integration (`agent-bench openclaw`, `openclaw-export`), `log_stream_monitor@1` task + reference agent, `run pairing` quick-start command with `--list`/`--all`/`--timeout`, `runs summary` table, `new-agent` scaffold, Web UI Pairings tab + `/api/pairings` endpoint, mock OpenClaw workspace example, `examples/simple_agent_demo/` POC app, expanded test suite (59 new tests).

### v0.7.0 — 2026-02-20
TraceCore Ledger & Record Mode Foundations: `ledger/manifest.schema.json` (formal JSON Schema for Ledger entries), `docs/ledger_governance.md` (contributor checklist + PR template + versioning policy), `runner/bundle.py` (baseline bundle writer with SHA-256 integrity), `runner/replay.py` (replay + strict enforcement), `agent-bench baseline --bundle`, `agent-bench bundle verify`, `agent-bench run --replay-bundle` / `--strict`, Web UI `/ledger` page + `/api/ledger` endpoint, Ruff linter integration, 15 new tests (160 total). `action_ts` and `budget_delta` added to trace entries (additive). `docs/record_mode.md` updated — replay and strict modes now implemented.

### v0.8.0
Record Mode complete: `agent-bench run --record` — runs the agent, verifies determinism by re-running, seals a baseline bundle, and rejects non-deterministic episodes. `check_record()` in `runner/replay.py` for raw run-to-run determinism comparison. 10 new tests (170 total). All three execution modes (record, replay, strict) now fully implemented.

### v0.9.1 — current
PyPI publish (`pip install tracecore`), sandbox allowlist enforcement (task manifest `[sandbox]` table, GuardedEnv filesystem + network guards, IO audit in record/replay/strict), runner validator snapshots (terminal payload normalized and persisted under `validator` key). 211 tests. Package metadata updated (`authors`, `[project.urls]`).
