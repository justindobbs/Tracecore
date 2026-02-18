# Changelog

All notable changes to this project will be documented here. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Published releases are tagged in
git (e.g., `v0.0.0-dev`, `v0.1.0`).

## [Unreleased]
### Added
- `tasks/log_stream_monitor@1`: new operations task — agent polls a paginated log stream, ignores noise entries, detects a `CRITICAL` entry, and emits `STREAM_CODE`. Primary record mode prototype target.
- `agents/log_stream_monitor_agent.py`: reference agent demonstrating patience + trigger detection across a multi-page stream.
- `agent-bench run pairing <name>`: quick-start CLI command to run a known-good agent+task pairing by name or auto-detect from CWD. `agent_bench/pairings.py` defines the `KnownPairing` registry and `find_pairing()` / `list_pairings()` helpers.
- `agent-bench run pairing --list`: print all known pairings in a rich table.
- `agent-bench run pairing --all`: batch-run every pairing in sequence and print a smoke-test summary table; exits non-zero if any pairing fails. Useful for CI after harness changes.
- `agent-bench run pairing --timeout N` / `agent-bench run --timeout N`: wall-clock timeout enforcement per run via a daemon thread; exits non-zero with a clear message if exceeded.
- `agent-bench runs summary`: compact `rich` table of recent runs (outcome, agent, task, seed, steps, tool calls, run ID prefix) with the same `--agent` / `--task` / `--limit` / `--failure-type` filters as `runs list`.
- `agent-bench new-agent <name>`: scaffold a new agent stub file with the correct `reset` / `observe` / `act` interface, inline docstrings, and budget-guard boilerplate. Supports `--output-dir` and `--force`.
- Web UI **Pairings** tab: one-click launch cards for every `KnownPairing`, with per-card seed input, last-run outcome chip (clickable → Trace Viewer), and `launchPairing()` JS that pre-fills the Run form without a page reload.
- `GET /api/pairings`: REST endpoint returning the full pairings registry with last-run history per entry; useful for CI scripts and notebooks.
- `tests/test_webui_routes.py`: 13 FastAPI route smoke tests using `TestClient` covering `GET /`, `/guide`, `/api/pairings`, `/api/traces/{id}`, `/traces/{id}`, and `/baselines/latest`.
- `tests/test_pairing_contracts.py`: 19 parametrized contract tests asserting every `KnownPairing` has a valid agent file, task directory, and manifest on disk.
- `tests/test_cli_new_agent.py`: 6 tests covering scaffold output, kebab/snake name normalisation, overwrite guard, `--force`, importability, and observe/act cycle.
- `agent-bench openclaw --agent-id <id>`: detects an OpenClaw agent from `openclaw.json` (CWD or `~/.openclaw/`), scaffolds a self-contained TraceCore adapter, and runs it against a task. Auto-detects the agent ID when only one named agent exists.
- `agent-bench openclaw --gateway`: additionally scaffolds a gateway-wired adapter that calls the OpenClaw gateway RPC (`agent` / `agent.wait`) per step.
- `agent-bench openclaw-export --agent-id <id>`: writes a certified bundle (`adapter_agent.py`, `gateway_adapter_agent.py`, `openclaw_agent.md`, `manifest.json`, `README.md`) to `tracecore_export/<id>/`. Blocked until a passing run exists for the adapter.
- `agent_bench/openclaw.py`: `detect_openclaw_agent()`, `scaffold_openclaw_adapter()`, `scaffold_gateway_adapter()`, `export_openclaw_agent()` — all the detection, scaffolding, and export logic.
- `tests/test_cli_openclaw.py`: 15 tests covering detection, auto-select, ambiguity guard, scaffold importability, gateway adapter, export manifest shape, prompt file copy, export-before-pass guard, and CLI command integration.

### Changed
- Web UI `_template_context()` now queries last-run history per pairing (using `failure_type is None` as success indicator) and exposes it to the Pairings panel.
- `_cmd_run()` delegates to `_run_with_timeout()` helper; zero overhead when `--timeout` is not passed.
- `get_task_options()` in `app.py` now parses `task.toml` files (in addition to legacy `task.yaml`) and filters tasks marked `internal: true`.

### Fixed
- `test_webui_context.py`: relaxed `fake_list_runs` mock to accept agent/task-scoped calls introduced by pairing history lookup.

### Documentation
- `docs/agents.md`: added `LogStreamMonitorAgent` entry with record mode relevance note.
- `SPEC_FREEZE.md`: added `log_stream_monitor@1` to frozen task table.
- `README.md`: updated Quick Start with `run pairing`, `--all`, `--timeout`, `runs summary`, and Pairings dashboard tab.
- `docs/tasks.md`: added `log_stream_monitor@1` catalog entry with skills, significance, and quick-start one-liner.
- `docs/troubleshooting.md`: added `run pairing` quick-start, `--timeout` enforcement, and `runs summary` sections to §2 CLI Invocation Errors.

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
