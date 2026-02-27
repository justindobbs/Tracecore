# Changelog

All notable changes to this project will be documented here. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Published releases are tagged in
git (e.g., `v0.0.0-dev`, `v0.1.0`).

## [Unreleased]

## [0.9.8] - 2026-02-27
### Fixed
- **WebUI agent loading**: Fixed `get_agent_options()` to use relative paths and work from any working directory, mirroring the tasks logic pattern
- **Directory independence**: Agent paths now display as `agents/chain_agent.py` instead of full absolute paths
- **Fallback behavior**: Properly falls back to bundled agents when local agents directory is not found

## [0.9.7] - 2026-02-27
### Fixed
- **WebUI agent loading**: Fixed `get_agent_options()` to use relative paths and work from any working directory, mirroring the tasks logic pattern
- **Directory independence**: Agent paths now display as `agents/chain_agent.py` instead of full absolute paths
- **Fallback behavior**: Properly falls back to bundled agents when local agents directory is not found

## [0.9.6] - 2026-02-26
### Added
- **Bundle trust pipeline**: Ed25519 signing of baseline bundles and the ledger registry via `agent_bench/ledger/signing.py`. Public key committed at `agent_bench/ledger/pubkey.pem` and bundled into the package.
- `agent-bench ledger verify` subcommand with three modes: `--registry` (verify top-level registry signature), `--entry <agent>` (verify all signed task rows), `--bundle <dir>` (verify a specific bundle directory).
- `agent_bench/ledger/stamp_registry()` helper — signs `registry.json` in-place using the `TRACECORE_LEDGER_SIGNING_KEY` env var.
- `.github/workflows/release.yml` — triggered on `v*` tags: runs unit tests, builds baseline bundles for reference agents, signs them, stamps the registry, builds the wheel, uploads signed `ledger-registry-<tag>.json` + wheel/sdist as GitHub Release assets, and publishes to PyPI.
- `GET /api/ledger` now surfaces provenance fields (`harness_version`, `published_at`, `bundle_sha256`, `bundle_signature`, `signed_at`) on every entry and task row.
- `cryptography>=42` added to core dependencies.
- `manifest.schema.json` extended with `bundle_sha256`, `bundle_signature`, `signed_at` fields at both the entry and task-row level.
- `docs/ledger.md` updated with trust evidence section, provenance field table, and `ledger verify` usage examples.
- `agents/sandboxed_code_auditor_agent.py`: reference agent for `sandboxed_code_auditor@1`. Reads `audit_scope.md` for `TARGET_KEY`, extracts `ISSUE_ID` from `src/runtime_guard.py` and `AUDIT_CODE` from `reports/audit.log` via `extract_value`, then emits `ISSUE_ID|AUDIT_CODE` via `set_output`.
- `runbook_verifier` and `sandboxed_code_auditor` pairings added to `agent_bench/pairings.py` (`agent-bench run pairing runbook_verifier` / `agent-bench run pairing sandboxed_code_auditor`).
- `runbook_verifier@1` and `sandboxed_code_auditor@1` added to `SPEC_FREEZE.md` frozen task table.
- `tests/test_sandboxed_code_auditor_agent.py`: two regression tests covering seed 0 and seed 42.
- `docs/agents.md`: added `RunbookVerifierAgent` and `SandboxedCodeAuditorAgent` entries to the catalog table and detail sections.
- `agent_bench/agents/runbook_verifier_agent.py` and `agent_bench/agents/sandboxed_code_auditor_agent.py` added to the bundled agents package so `pip install tracecore` users and the dashboard pairing panel resolve them correctly via the loader fallback.
- `GUIDE_ENTRIES` in `agent_bench/webui/app.py` updated to include `runbook_verifier_agent` and `sandboxed_code_auditor_agent` so they appear in the dashboard Guide tab.

## [0.9.5] - 2026-02-25
### Added
- `agent_bench/agents/` subpackage bundling all reference agents (`toy_agent`, `log_stream_monitor_agent`, `ops_triage_agent`, `rate_limit_agent`, `chain_agent`) into the published wheel. Users who `pip install tracecore` now have agents available immediately — no local `agents/` directory needed.

### Fixed
- `agent-bench dashboard` agent dropdown was empty on a fresh PyPI install. `get_agent_options()` now falls back to the bundled `agent_bench/agents/` package when no local `agents/` dir exists.
- `agent-bench dashboard` task dropdown was empty on a fresh PyPI install. `get_task_options()` now falls back to the bundled registry (`list_task_descriptors()`) when no local `tasks/` dir exists.

## [0.9.4] - 2026-02-25
### Changed
- `fastapi`, `uvicorn`, `jinja2`, and `python-multipart` promoted from optional `[dev]` extras to core `dependencies` so that `pip install tracecore` includes everything needed to run `agent-bench dashboard` out of the box.
- Added `notebooks/dashboard_walkthrough.ipynb`: two-cell notebook that installs TraceCore and launches the dashboard.

## [0.9.3] - 2026-02-25
### Added
- Colab quickstart notebook (`examples/tracecore_quickstart.ipynb`): install TraceCore, write a minimal agent, run `filesystem_hidden_config@1` with per-step trace output, inspect results, and list all tasks — runnable end-to-end from Google Colab or any Jupyter environment.
- `README.md` Quick links now surfaces the Colab quickstart notebook as the fastest on-ramp.

### Fixed
- Packaging regression from v0.9.1: wheels published to PyPI were missing the `agent_bench.runner.*` modules, causing `ModuleNotFoundError: agent_bench.runner` whenever `agent-bench interactive` imported `runner.baseline`. `pyproject.toml` now includes every `agent_bench.*` subpackage so `pip install tracecore` / `uv pip install tracecore` (including the Colab quickstart flow) ship a complete harness.
- `tasks/registry.json` and all task manifests (`task.toml`, `task.yaml`) were not included in published wheels, causing `FileNotFoundError: Task not found` in Colab and any other pip-installed environment. Fixed by adding `[tool.setuptools.package-data]` entries for `tasks`, `agent_bench.webui`, and `agent_bench.ledger`.
- `REGISTRY_PATH` in `agent_bench/tasks/registry.py` used a relative `Path(__file__).parent.parent.parent` walk that resolved to `site-packages/` root in pip installs instead of the `tasks/` package directory. Now uses `importlib.resources.files("tasks")` with a fallback for editable installs.
- `agent_bench/webui/app.py` FastAPI banner version bumped to `0.9.3` to match `pyproject.toml`.

## [0.9.1] - 2026-02-24
### Added
- Published `tracecore 0.9.1` to PyPI (`pip install tracecore` / `uv pip install tracecore`). Package name is `tracecore`; CLI entry point remains `agent-bench` for backward compatibility. `pyproject.toml` updated with `authors`, `[project.urls]` (Homepage, Issues), and `[[tool.uv.index]]` for TestPyPI dry-run workflow. `README.md` and `CONTRIBUTING.md` updated to advertise the published install path as primary.
- Task manifest `[sandbox]` table: deterministic tasks now require `filesystem_roots` (array of absolute path prefixes) and `network_hosts` (array of literal/wildcard hostnames) declarations. Registry validation (`agent_bench/tasks/registry.py`) enforces presence and type correctness, normalizes entries, and propagates metadata to loaders. All 10 deterministic task manifests updated with sandbox allowlists.
- `agent_bench/tasks/registry.py`: `_default_sandbox()`, `_normalize_fs_root()`, `_normalize_host_entry()`, `_normalize_sandbox()` functions to parse and validate sandbox declarations from task manifests.
- `agent_bench/tasks/loader.py`: exposes `sandbox` metadata in loaded task dictionaries for runtime consumption.
- `agent_bench/env/environment.py`: GuardedEnv enforces filesystem allowlists, adds a `NetworkGuard` utility for host allowlists, and exposes `require_network()` for controlled outbound calls.
- `agent_bench/runner/runner.py`: wires task sandbox allowlists into GuardedEnv and includes sandbox metadata in the task spec passed to agents.
- `tests/test_sandbox_env.py`: coverage for filesystem allowlist enforcement and network host matching.
- IO audit enforcement for record/replay/strict: per-step filesystem/network access is recorded as `io_audit` entries in the action trace and `tool_calls.jsonl`, compared during `check_record`/`check_replay`/`check_strict`, and validated against sandbox allowlists.
- Bundle manifests now mirror `sandbox` declarations; `agent-bench bundle verify` rejects bundles missing sandbox metadata or containing disallowed IO audit entries.
- Replay/strict checks reject sandbox mismatches between bundles and live runs; record mode rejects runs missing sandbox declarations.
- New regression tests covering bundle audit verification, replay audit mismatches, and network guard scheme/port validation.
- Runner validator snapshots: terminal validator payloads are normalized (taxonomy fallback, message/error propagation) and persisted under the run result `validator` key, ensuring bundles capture the exact validator verdict. Added tests guarding invalid failure_type overrides plus documentation updates in `docs/trace_artifacts.md` and `docs/runner.md`.
- Web UI (`agent_bench/webui/app.py`): Pydantic response models (`PairingSummary`, `LedgerEntryPayload`, `TraceRunPayload`, `ErrorPayload`), `_summarize_io_audit()` helper for per-run IO audit summaries, `_strip_io_audit()` for trace API responses, `baseline_submitted` context variable, `/api/traces/{run_id}?include_io=true` flag.

### Fixed
- `agent_bench/integrations/langchain_adapter.py`: generated agent source had `IndentationError` due to `textwrap.dedent()` stripping the common 8-space leading indent from the indented f-string template, producing a module-level docstring indented 8 spaces. Replaced `dedent(f'''...''')` with line-by-line f-strings anchored at column 0. All three `test_langchain_adapter` tests now pass.

## [0.8.0] - 2026-02-20
### Added
- `agent-bench run --record`: record mode implementation. Runs the agent once, seals a baseline bundle, re-runs to verify determinism, and deletes the bundle if the two runs diverge. Exits 0 with `[RECORD OK]` on success; exits 1 with `[RECORD FAILED: NonDeterministic]` if the episode is non-deterministic, or `[RECORD REJECTED]` if the first run did not succeed. Mutually exclusive with `--replay-bundle` and `--strict`.
- `agent_bench/runner/replay.py` `check_record(run_a, run_b)`: compares two raw run result dicts for determinism (success, termination_reason, failure_type, step count, per-step action+result). Returns `{"ok": bool, "errors": list[str], "mode": "record"}`.
- `tests/test_record_mode.py`: 10 tests covering `check_record` unit cases (identical, success mismatch, termination mismatch, step count mismatch, action mismatch, result mismatch, empty traces) and CLI integration cases (deterministic agent seals bundle, non-deterministic agent rejects and deletes bundle, failed run rejected).

## [0.7.0] - 2026-02-20
### Added
- `tests/test_runner_failure_taxonomy.py`: 10 regression tests covering the full runner failure taxonomy — terminal validator `logic_failure` path (default and explicit fields), `budget_exhausted` (steps and tool calls), `invalid_action`, and success (`failure_type=None`). Verifies `failure_type`, `termination_reason`, and `failure_reason` are emitted correctly for every terminal branch.
- `agent_bench/ledger/manifest.schema.json`: formal JSON Schema (draft 2020-12) for Ledger entries. Defines required fields (`agent`, `description`, `suite`, `tasks`), optional certification fields (`harness_version`, `seed_policy`, `published_at`, `maintainer`), and per-task baseline rows (`task_ref`, `success_rate`, `avg_steps`, `run_artifact`, etc.).
- `docs/ledger_governance.md`: contributor checklist, required/recommended metadata examples, PR template, versioning policy, suite definitions, and relationship to trust evidence bundles. Defines the governance model for submitting and maintaining Ledger entries.
- Ruff lint-only configuration (`ruff>=0.9.0` in `.[dev]`, `[tool.ruff.lint]` in `pyproject.toml`, scoped to `agent_bench/`). CI step added to `tests.yml` before pytest.
- `agent_bench/runner/bundle.py`: baseline bundle writer. `write_bundle(result)` produces a `<run_id>/` directory under `.agent_bench/baselines/` containing `manifest.json` (run metadata), `tool_calls.jsonl` (one line per trace entry), `validator.json` (final validation snapshot), and `integrity.sha256` (SHA-256 hashes). `verify_bundle(bundle_dir)` checks all hashes and returns `{"ok": bool, "errors": list}`.
- `runner.py` trace entries now include `action_ts` (UTC ISO 8601 timestamp of action dispatch) and `budget_delta` (`{"steps": 1, "tool_calls": 1}`) — additive fields, no breaking changes.
- `docs/trace_artifacts.md`: documented new `action_ts` and `budget_delta` trace entry fields; added full Baseline Bundle Format section (layout, per-file schemas, Python API, integrity format).
- `agent-bench baseline --bundle`: new flag that writes a baseline bundle for the most recent matching run to `.agent_bench/baselines/<run_id>/` and prints `{"bundle_dir": ..., "run_id": ...}`.
- `agent-bench bundle verify <path>`: new subcommand that verifies SHA-256 integrity of a bundle directory. Exits 0 on pass, 1 on failure. Supports `--format json` for machine-readable output.
- `agent_bench/runner/replay.py`: replay enforcement module. `check_replay(bundle_dir, result)` diffs a fresh run against a baseline bundle (success, termination_reason, failure_type, per-step action+result). `check_strict(bundle_dir, result)` adds budget invariants (steps_used and tool_calls_used must not exceed baseline). Both return `{"ok": bool, "errors": list[str], "mode": str}`.
- `agent-bench run --replay-bundle <BUNDLE_DIR>`: re-runs the agent using agent/task/seed from the bundle manifest, then enforces replay rules. Exits 1 and prints divergences if the trace mismatches.
- `agent-bench run --strict`: adds budget enforcement on top of `--replay-bundle` (steps_used and tool_calls_used must not exceed baseline).
- `docs/record_mode.md`: updated status banner (replay + strict now implemented), added `## CLI (implemented)` section with copy-pastable commands, updated developer workflow and mode table.
- `GET /api/ledger`: new FastAPI endpoint returning the full Ledger registry as a JSON array.
- `GET /ledger`: new Ledger page in the web UI dashboard — shows registered agent count, task baseline count, suite count, per-entry cards with success-rate bar charts, live client-side search filter, and a machine-readable API hint.
- Ledger nav link added to the `index.html` rail (between Pairings and Guide).
- `tests/test_webui_routes.py`: 5 new tests covering `/api/ledger` (JSON shape) and `/ledger` (200, agent listing, API hint).

### Fixed
- `tests/test_determinism.py` `_strip_metadata`: now also strips `action_ts` from each `action_trace` entry so wall-clock timestamps don't cause false determinism failures.
- `runner/baseline.py` `diff_runs`: normalize trace entries before comparison by stripping `action_ts` and `budget_delta` so old baseline artifacts (pre-v0.7.0) don't produce false step divergences in `agent-bench baseline --compare` and the `chain-agent-baseline` CI workflow.

## [0.6.0] - 2026-02-19
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
- `agent-bench openclaw-export --agent-id <id>`: writes a certified bundle (`<id>_adapter_agent.py`, `<id>_gateway_adapter_agent.py`, `AGENTS.md`, `openclaw.json`, `manifest.json`, `README.md`) to `tracecore_export/<id>/`. Blocked until a passing run exists for the adapter. Bundle adapters are for **optional regression testing** — not deployment; the OpenClaw agent continues to run normally in OpenClaw.
- `agent_bench/openclaw.py`: `detect_openclaw_agent()`, `scaffold_openclaw_adapter()`, `scaffold_gateway_adapter()`, `export_openclaw_agent()` — all the detection, scaffolding, and export logic.
- `tests/test_cli_openclaw.py`: 21 tests covering detection (both config formats), auto-select, ambiguity guard, model string normalisation, `default=true` selection, scaffold importability, gateway adapter, export manifest shape, prompt file copy, `openclaw.json` copy, export-before-pass guard, CLI command integration, and mock workspace detection.
- `examples/mock_openclaw_workspace/`: a self-contained mock OpenClaw workspace (`openclaw.json` + `workspace/AGENTS.md` + `cron/jobs.json`) for trying the full `agent-bench openclaw` workflow without an OpenClaw install. Agent: `log-monitor` (log triage + rate-limit watchdog), maps to `log_alert_triage@1` and `rate_limited_api@1`.
- `OPENCLAW_QUICKSTART.md`: root-level 5-minute quickstart for OpenClaw users — scaffold, AI IDE red-green loop, task selection table, export, links to full tutorial and official OpenClaw docs.
- `examples/simple_agent_demo/`: proof-of-concept standalone demo app showing the full TraceCore agent execution loop — load task, load agent, run episode, display results. Includes `demo.py` CLI with `--list-tasks`, `--list-agents`, `--verbose`, `--seed` flags; `README.md`; `QUICKSTART.md`; and Windows/Unix launcher scripts.

### Changed
- Web UI `_template_context()` now queries last-run history per pairing (using `failure_type is None` as success indicator) and exposes it to the Pairings panel.
- `_cmd_run()` delegates to `_run_with_timeout()` helper; zero overhead when `--timeout` is not passed.
- `get_task_options()` in `app.py` now parses `task.toml` files (in addition to legacy `task.yaml`) and filters tasks marked `internal: true`.

### Fixed
- `test_webui_context.py`: relaxed `fake_list_runs` mock to accept agent/task-scoped calls introduced by pairing history lookup.

### Documentation
- `docs/agents.md`: added `LogStreamMonitorAgent` entry with record mode relevance note and summary table row.
- `SPEC_FREEZE.md`: updated header to `v0.6.0`; `log_stream_monitor@1` added to frozen task table.
- `README.md`: updated Quick Start with `run pairing`, `--all`, `--timeout`, `runs summary`, Pairings dashboard tab, and `examples/` callout.
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
