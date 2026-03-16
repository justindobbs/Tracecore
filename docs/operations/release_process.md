# Release Process

This document describes the standard checklist for cutting a TraceCore release. Follow these steps in order for every version bump.

## Release checklist

1. **Finalize changelog** — Move all `## [Unreleased]` entries into a new `## [X.Y.Z] - YYYY-MM-DD` section in `CHANGELOG.md`. Leave empty `[Unreleased]` placeholders for the next cycle. If any changes touched the CLI contracts, artifact schema, or bundle layout, ensure `docs/specs/contract_spec.md`, `docs/specs/core.md`, and `CHANGELOG.md` describe them explicitly.

2. **Verify behavior** — Complete every step in [`docs/operations/manual_verification.md`](manual_verification.md) and record the resulting `run_id` values. These become the reproducible proof of behavior for the release.

3. **Stamp versions** — Update the runtime/package version string in:
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `agent_bench/webui/app.py` → `version="X.Y.Z"` in the `FastAPI(...)` constructor

   Then run a task and confirm the artifact reports `"harness_version": "X.Y.Z"`. Spec versions remain independent; only update `agent_bench/spec/tracecore-spec-*.md` when the normative contracts change.

4. **Run tests** — Execute the required release suite and ensure all commands pass:
   - `python -m pytest`
   - `python -m ruff check agent_bench`
   - Additional targeted tests for any new agent/runtime behavior, integrations, or performance-sensitive coordination changes

   For Phase 6 distributed-style execution coverage, also confirm the nightly workflow `.github/workflows/nightly-distributed-acceptance.yml` still reflects the intended `tracecore run batch` acceptance slice before release.
   For performance-sensitive changes that touch the harness or batch execution path, generate and review the current `deliverables/perf/` artifacts using [`docs/operations/performance_baselines.md`](performance_baselines.md).

5. **Validate tasks** — `tracecore tasks validate --registry` (or `agent-bench tasks validate --registry` if validating the legacy alias) — must exit 0.

6. **Update SPEC_FREEZE.md** — Confirm the header version and task table reflect the release. Add any new frozen tasks; mark any newly internal tasks in the experimental section. If the spec itself changed, update `agent_bench/spec/tracecore-spec-*.md`, `agent_bench/spec/artifact-schema-*.json`, `agent_bench/spec/compliance-checklist-*.md`, and `agent_bench/spec/determinism.md` together and document the new spec version.

7. **Produce trust evidence bundle** — Per `SPEC_FREEZE.md` rule 4, create `deliverables/trust_bundle_vX.Y.Z/` containing:
   - `metadata.json` (harness version, git SHA, task list, seed policy)
   - Representative run artifacts referenced in release notes
   - Baseline exports used for gating

8. **Contract acknowledgement** — Reread `docs/specs/contract_spec.md` and confirm the release either (a) leaves the spec untouched, or (b) includes the required major/minor bump and `agent_bench/spec/` updates per the "Breaking Change Procedure" section. Record the runtime version + implemented spec version in the release PR description.

9. **Tag & push**:
   ```sh
   git tag -a vX.Y.Z -m "TraceCore vX.Y.Z"
   git push origin vX.Y.Z
   ```
   Before tagging, confirm the release commit is pushed, CI is green, and the tag annotation calls out the key changes plus any migration notes.

## GitHub CLI workflow helpers

Maintainers who use the GitHub CLI can inspect or rerun Actions workflows without leaving the terminal:

- List recent workflow runs:
  ```sh
  gh run list --limit 10
  ```

- Rerun a failed workflow or only its failed jobs:
  ```sh
  gh run rerun <run-id>
  gh run rerun <run-id> --failed
  ```

- Watch a run after rerunning it:
  ```sh
  gh run watch <run-id>
  ```

- Manually dispatch the nightly workflows:
  ```sh
  gh workflow run nightly.yml
  gh workflow run nightly-distributed-acceptance.yml
  ```

Use `gh auth status` first if the CLI is not already authenticated against the repository.

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

### v0.9.1 — 2026-03-04
PyPI publish (`pip install tracecore`), sandbox allowlist enforcement (task manifest `[sandbox]` table, GuardedEnv filesystem + network guards, IO audit in record/replay/strict), runner validator snapshots (terminal payload normalized and persisted under `validator` key). 211 tests. Package metadata updated (`authors`, `[project.urls]`).

### v1.1.1 — 2026-03-05
Dependency/security refresh: `tracecore[pydantic_poc]` now requires `pydantic-ai>=1.66.0`, `tracecore[openai_agents]` now bundles `openai-agents>=0.10.4`, and maintainer subprocess execution now forces `shell=False`.

### v1.1.2 — 2026-03-06
Release-process and documentation polish: release instructions now point at the current docs/spec layout, release validation explicitly includes Ruff and task-registry checks, and README release-facing links now resolve to the current `docs/` and `agent_bench/spec/` paths.

### v1.1.3 — current
OpenAI onboarding and runtime-hardening release: added `tracecore init openai-agents`, tightened the native `tracecore` onboarding loop in the docs and post-run guidance, exposed first-pass `Your project` versus bundled discovery groupings in the dashboard, and unified single-run plus batch timeout enforcement around the subprocess-based isolation path with focused regression coverage.
