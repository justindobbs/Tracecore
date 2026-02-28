# TraceCore Compliance Checklist v0.1

An implementation is conformant with TraceCore Specification v0.1 if every episode satisfies the following verifiable items. This checklist is designed for auditors, CI systems, and runtime developers.

## Episode lifecycle
- [ ] Inputs frozen before execution: `agent_ref`, `task_ref`, `task_version`, `seed`, `budgets`, `spec_version`.
- [ ] Task harness materials hashed and recorded (`task_hash`).
- [ ] Observe → act → execute → validate loop enforced in order.
- [ ] Budgets enforced at each step (no actions when any budget reaches zero).
- [ ] Validator invoked according to task declaration and emits structured payloads.

## Determinism declarations
- [ ] `determinism.seed` recorded and equals the runtime seed input.
- [ ] Tooling section lists every external model/provider plus versions.
- [ ] Mocked integrations or blocked IO surfaces are documented.
- [ ] Replay tooling (`--record`, `--strict`, etc.) available to prove determinism.

## Artifact validation
- [ ] Artifact JSON validates against `/spec/artifact-schema-v0.1.json`.
- [ ] Artifact includes `spec_version` and `runtime_identity`.
- [ ] `action_trace` contains observation, action, result, IO audit, and budget deltas for every step.
- [ ] Validator snapshot embedded verbatim.
- [ ] `artifact_hash` computed and stored; hash verifiable from serialized bytes.

## Taxonomy & termination
- [ ] `termination_reason` originates from the canonical taxonomy in `docs/core.md`.
- [ ] `failure_type` is one of `budget_exhausted`, `invalid_action`, `sandbox_violation`, `logic_failure`, `timeout`, `non_termination`, or `null` on success.
- [ ] Trace records include validator-derived context for `logic_failure` cases.

## Versioning & metadata
- [ ] Runtime declares the spec version it implements (CLI flag, artifact metadata, API).
- [ ] Spec version is independent from package/runtime version.
- [ ] Task hashes and versions recorded for every run.
- [ ] Optional extensions (e.g., extra metrics) do not override or remove required fields.

## Compliance automation
- [ ] Runtime exposes a strict compliance mode (e.g., `tracecore run --strict-spec`) that refuses to report success unless every checklist item passes.
- [ ] CI workflows reference this checklist or equivalent automation before publishing artifacts or baselines.
