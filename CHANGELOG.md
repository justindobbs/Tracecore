# Changelog

All notable changes to this project will be documented here. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Published releases are tagged in
git (e.g., `v0.0.0-dev`, `v0.1.0`).

## [Unreleased]
### Added
- _Nothing yet_

### Changed
- _Nothing yet_

### Documentation
- _Nothing yet_

## [0.5.0] - 2026-02-18
### Added
- `scripts/policy_gate.py`: minimal CI policy gate script enforcing success, step, and tool-call thresholds against run artifacts and baselines.
- `CONTRIBUTING.md`: top-level contributor guide covering task authoring, bug fixes, PR checklist, and code style.
- `SECURITY.md`: security policy documenting sandbox scope, in-process isolation model, and vulnerability reporting process.
- `docs/release_process.md`: canonical release checklist (replaces inline checklists in README) with historical release notes.

### Changed
- `dice_game` task marked `"internal": true` in `tasks/registry.json`; excluded from frozen spec (documented in `SPEC_FREEZE.md` experimental section).
- `pydantic-ai` version bound tightened to `>=0.0.3,<1.0` to prevent silent breakage.
- CHANGELOG ordering corrected: `[0.3.0]` now appears after `[0.2.0]` chronologically.
- `SPEC_FREEZE.md` header updated from `v0.4.0` to `v0.4.1` to match the released version.

### Fixed
- Removed references to unimplemented CLI flags (`--budget`, `--verbose`, `--agent-class`) and the `runs show` subcommand from README and `docs/troubleshooting.md`.
- `--budget` note added to README clarifying budgets are task-manifest-defined, not CLI-overridable.
- `--reload` dev-only warning added to README and `docs/troubleshooting.md`.

### Documentation
- `docs/record_mode.md`: added "Status: Future Vision — Not Yet Implemented" banner.
- `docs/core.md` and `agent_bench/runner/failures.py`: clarified `non_termination` is reserved and never emitted by the current runner.
- README inline release checklists (v0.1.0–v0.3.0) replaced with a pointer to `docs/release_process.md`.

## [0.4.1] - 2026-02-16
### Added
- Operations suite tasks: `log_alert_triage@1`, `config_drift_remediation@1`, and `incident_recovery_chain@1`.
- Reference `OpsTriageAgent` for operations triage scenarios.
- Task contract specification documentation and CLI task validation (`agent-bench tasks validate`).

### Changed
- Runner now honors validator-declared terminal failures to emit `logic_failure` outcomes when validators opt in to `terminal: true`.

### Documentation
- Updated docs and UI copy to reference the TraceCore brand while keeping the `agent-bench` CLI/package name for compatibility.
- Added long-term roadmap clarity, contract spec guidance, and trust evidence bundle requirements.

## [0.2.0] - 2026-02-14
### Added
- Structured failure taxonomy (`failure_type`) emitted by the runner and persisted in
  run artifacts to enable meaningful diagnostics. @agent_bench/runner/failures.py#1-60
  @agent_bench/runner/runner.py#70-294
- CLI support for filtering runs by failure buckets via `agent-bench runs list
  --failure-type <bucket>`. @agent_bench/cli.py#1-82 @agent_bench/runner/runlog.py#30-87
- Web UI "Recent Runs" labels now show `Success` vs. `Failure - <type>` to mirror the
  taxonomy. @agent_bench/webui/templates/index.html#428-447
- Automated test covering the new CLI filter behavior. @tests/test_cli_runs.py#1-40

### Documentation
- README instructions for using the `--failure-type` flag and description of how the UI
  surfaces the same buckets. @README.md#169-189
- OpenClaw quickstart tutorial for adapter patterns and first-run guidance.
  @tutorials/openclaw_quickstart.md#1-80

## [0.3.0] - 2026-02-15
### Added
- Task manifest schema v0.1 (`task.toml`) with loader validation and example docs.
- Determinism regression tests covering repeated runs + failure modes.
- Baseline compare enhancements: JSON output and CI-friendly exit codes.
- Trace artifact schema documentation + changelog policy for schema changes.
- `agent-bench.toml` configuration with per-agent override blocks.
- GitHub Actions reusable workflow for run+compare with artifacts upload.

### Documentation
- CLI/config docs for `agent-bench.toml`, `baseline --compare`, and CI usage.
- Updated task/spec references to include shipped tasks and versions.

## [0.1.0] - 2026-01-15
### Added
- Initial public release of Agent Bench with filesystem and rate-limited API tasks,
  baseline FastAPI UI, and reference agents.

### Fixed
- Early polish passes on README installation instructions and task specs.

> Note: Dates are illustrative; update them when cutting an actual release. When preparing a
> release, add a `git tag vX.Y.Z` matching the section heading.
