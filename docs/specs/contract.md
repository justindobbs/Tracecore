---
description: TraceCore compatibility & artifact contract
version: 0.8.0
---

# TraceCore Compatibility Contract

This document defines the public contract for TraceCore's CLI, artifact formats, and trust evidence so consumers can rely on deterministic behavior across releases.

## Scope

The contract covers four surfaces:

1. **CLI + flags** — `agent-bench run`, `agent-bench baseline`, `agent-bench bundle`, and task/registry commands used in CI.
2. **Run artifacts** — `.agent_bench/runs/<run_id>.json` as defined in [`docs/trace_artifacts.md`](trace_artifacts.md).
3. **Baseline bundles** — `.agent_bench/baselines/<run_id>/` contents (manifest, tool calls log, validator snapshot, integrity file).
4. **Trust evidence** — release bundles referenced in [`SPEC_FREEZE.md`](../SPEC_FREEZE.md) and release notes.

## Versioning & Deprecation Policy

TraceCore follows semantic versioning for all contract surfaces:

- **Patch (`0.8.x`)** — bug fixes and doc clarifications; no contract changes.
- **Minor (`0.x+1.0`)** — additive CLI flags or artifact fields that are backwards compatible.
- **Major (`1.0.0`)** — required for any breaking change (removing CLI flags, renaming artifact fields, altering bundle layout).

Breaking changes must:

1. Bump `pyproject.toml` / harness version accordingly.
2. Update this document with the new contract definition and version header.
3. Call out the change in `CHANGELOG.md` and release notes.
4. Provide migration guidance (e.g., how to re-record bundles).

## CLI Contract

| Command | Stable Flags | Guarantees |
| --- | --- | --- |
| `agent-bench run` | `--agent`, `--task`, `--seed`, `--record`, `--replay-bundle`, `--strict`, `--timeout` | Flag semantics will not change without a version bump. `--record` always runs exactly twice (capture + verification). `--replay-bundle` and `--strict` require a baseline bundle path and enforce the same comparison rules described in `docs/record_mode.md`. |
| `agent-bench baseline --bundle` | `--agent`, `--task`, `--seed`, `--bundle`, `--dest` | Produces the bundle layout described below; existing files are never mutated silently. |
| `agent-bench bundle verify` | `<bundle_path>`, `--format json` | Verification output schema (`{"ok": bool, "errors": []}`) is stable. |
| `agent-bench tasks validate --registry` | N/A | Emits deterministic validation results (no network/file writes) so CI policies can rely on it. |

Constraints:
- New flags may be added, but removals or semantic changes require a major version bump or a deprecation window documented in the changelog.
- Default seeds (`--seed`) and timeout handling must remain deterministic.

## Run Artifact Schema

- Canonical schema lives in [`docs/trace_artifacts.md`](trace_artifacts.md).
- Additive top-level or trace-entry fields are allowed; removals/renames require a major version bump.
- `harness_version` identifies the contract; tooling should validate this field before diffing artifacts.
- Action/result payloads remain task-defined; only the envelope fields listed in the schema are governed by this contract.

## Baseline Bundle Contract

A baseline bundle consists of:

```
.agent_bench/baselines/<run_id>/
    manifest.json
    tool_calls.jsonl
    validator.json
    integrity.sha256
```

Commitments:
- `manifest.json` contains the metadata set documented in [`docs/trace_artifacts.md`](trace_artifacts.md) (`trace_entry_count` included).
- `tool_calls.jsonl` contains one JSON line per trace entry with the same envelope as the run artifact.
- `validator.json` preserves `success`, `termination_reason`, `failure_type`, `failure_reason`, and `metrics`.
- `integrity.sha256` is a standard `sha256sum` output that allows tamper detection.
- Bundle writers never modify prior bundles in place; repeats produce new directories.

## Trust Evidence & SPEC Freeze

- Frozen tasks are listed in [`SPEC_FREEZE.md`](../SPEC_FREEZE.md).
- Each release must publish `deliverables/trust_bundle_vX.Y.Z/` with the metadata described in `SPEC_FREEZE.md` and reference it in the changelog/release notes.
- Re-recording a frozen task requires bumping its version and updating `SPEC_FREEZE.md`.

## Breaking Change Procedure

1. Propose the change with motivation and migration notes.
2. Update `docs/contract.md` (this file) with the new definitions and increment the `version` frontmatter.
3. Update `docs/trace_artifacts.md`, `docs/record_mode.md`, or other affected specs.
4. Bump `pyproject.toml` / harness version.
5. Update release documentation (`docs/release_process.md`, changelog) and trust evidence requirements.
6. Re-run the full test suite plus any new regression coverage for the changed surface.

## Release Checklist Hooks

- `docs/release_process.md` references this contract; publishing a release requires confirming no breaking changes were introduced without the required version bump.
- `tests/test_contract_doc.py` ensures the harness version matches the contract version so documentation stays in sync.

---

_Last updated for TraceCore v0.8.0._
