# Release Process

This document describes the standard checklist for cutting a TraceCore release. Follow these steps in order for every version bump.

## Release checklist

1. **Finalize changelog** — Move all `## [Unreleased]` entries into a new `## [X.Y.Z] - YYYY-MM-DD` section in `CHANGELOG.md`. Leave empty `[Unreleased]` placeholders for the next cycle.

2. **Verify behavior** — Complete every step in [`docs/manual_verification.md`](manual_verification.md) and record the resulting `run_id` values. These become the reproducible proof of behavior for the release.

3. **Stamp versions** — Update the version string in:
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `agent_bench/webui/app.py` → `version="X.Y.Z"` in the `FastAPI(...)` constructor

   Then run a task and confirm the artifact reports `"harness_version": "X.Y.Z"`.

4. **Run tests** — `python -m pytest` — all tests must pass.

5. **Validate tasks** — `agent-bench tasks validate --registry` — must exit 0.

6. **Update SPEC_FREEZE.md** — Confirm the header version and task table reflect the release. Add any new frozen tasks; mark any newly internal tasks in the experimental section.

7. **Produce trust evidence bundle** — Per `SPEC_FREEZE.md` rule 4, create `deliverables/trust_bundle_vX.Y.Z/` containing:
   - `metadata.json` (harness version, git SHA, task list, seed policy)
   - Representative run artifacts referenced in release notes
   - Baseline exports used for gating

8. **Tag & push**:
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

### v0.6.0 — current
OpenClaw integration (`agent-bench openclaw`, `openclaw-export`), `log_stream_monitor@1` task + reference agent, `run pairing` quick-start command with `--list`/`--all`/`--timeout`, `runs summary` table, `new-agent` scaffold, Web UI Pairings tab + `/api/pairings` endpoint, mock OpenClaw workspace example, `examples/simple_agent_demo/` POC app, expanded test suite (59 new tests).
