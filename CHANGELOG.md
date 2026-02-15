# Changelog

All notable changes to this project will be documented here. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project aims to follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html). Published releases are tagged in
git (e.g., `v0.0.0-dev`, `v0.1.0`).

## [Unreleased]
### Added

### Documentation
- Updated docs and UI copy to reference the TraceCore brand while keeping the `agent-bench` CLI/package name for compatibility.

## [0.3.0] - 2026-03-15
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

## [0.1.0] - 2026-01-15
### Added
- Initial public release of Agent Bench with filesystem and rate-limited API tasks,
  baseline FastAPI UI, and reference agents.

### Fixed
- Early polish passes on README installation instructions and task specs.

> Note: Dates are illustrative; update them when cutting an actual release. When preparing a
> release, add a `git tag vX.Y.Z` matching the section heading.
