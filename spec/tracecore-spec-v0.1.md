# TraceCore Specification v0.1

TraceCore v0.1 is the normative specification for deterministic agent execution. It defines the contracts that any conforming runtime, harness, or tooling must satisfy in order to emit TraceCore-compliant artifacts. This document is intentionally formal; all explanatory or marketing content lives outside `/spec/`.

## 1. Purpose
1. Establish a deterministic execution standard for autonomous agent systems.
2. Enable independent teams to build interoperable runtimes and tooling that exchange TraceCore artifacts without loss of fidelity.
3. Provide auditors with a portable evidence format that can be validated offline.

## 2. Definitions
- **Episode** — A bounded execution of an agent against a task, parameterized by `agent_ref`, `task_ref`, `seed`, `budgets`, and `runtime_identity`.
- **Task** — A deterministic harness defined by `setup.py`, `actions.py`, `validate.py`, and `task.toml`, including sandbox allowlists and budgets.
- **Budget** — The set of quantitative limits (`steps`, `tool_calls`, optional `wall_clock_seconds`) that guarantee termination.
- **Validator** — Deterministic code that inspects task state and emits binary verdicts and structured payloads used to classify termination.
- **Artifact** — The canonical JSON record of an episode, conforming to `/spec/artifact-schema-v0.1.json`.

## 3. Execution Lifecycle
Every TraceCore episode MUST execute the following ordered stages. Deviations are non-compliant.
1. **Resolve identities** — Freeze `agent_ref`, `task_ref`, `task_version`, `seed`, `budgets`, and `spec_version`. These inputs are immutable for the duration of the episode.
2. **Load deterministic task** — Materialize the task harness described by `task_ref`. Hashes of task files SHALL be recorded in the artifact.
3. **Initialize agent** — Call the reference interface with the immutable task specification and budgets.
4. **Interact** — Repeat the observe → act → execute loop while budgets remain. Observations SHALL include remaining budget deltas.
5. **Validate** — Invoke the validator after each action (inline) or at declared checkpoints. Validators MUST emit `{ "ok": bool, "terminal": bool, "details": object }`.
6. **Terminate** — Emit `termination_reason` and `failure_type` drawn from the canonical taxonomy defined in `docs/core.md`.
7. **Persist artifact** — Write the artifact atomically and compute its content hash for integrity checks.

## 4. Determinism Requirements
1. **Seeded determinism** — Given identical inputs (agent code, task version, seed, budgets, runtime identity) the runtime SHALL emit the same sequence of actions, observations, and validator decisions.
2. **Replay determinism** — Implementations MUST provide a means to rerun an artifact (`--replay`, bundle verification, etc.) and produce identical outcomes or a structured incompatibility reason.
3. **Tool mocking** — Any external IO (network, filesystem outside allowlists) MUST be mocked or blocked so traces remain reproducible.
4. **Model version pinning** — LLM or model dependencies SHALL record provider, model identifier, and shim version in the artifact. Non-pinned models are non-compliant.
5. **Clock control** — Timestamps SHALL be sourced from monotonic, deterministic clocks when possible. Wall-clock timestamps are permitted but must be UTC ISO8601.
6. **Non-compliance** — Detectable nondeterminism (e.g., diverging traces across replays) MUST be surfaced as `failure_type=non_deterministic` or equivalent rejection.

## 5. Artifact Requirements
1. Artifacts SHALL conform to `/spec/artifact-schema-v0.1.json`.
2. Every artifact MUST include `spec_version`, `task_hash`, `agent_ref`, `runtime_identity`, and the full `action_trace`.
3. Each trace entry SHALL record observation, action, result, IO audit, and budget deltas.
4. Validator payloads MUST be embedded verbatim.
5. Artifacts SHALL embed a deterministic `artifact_hash` computed over the serialized payload (recommended SHA-256).
6. Artifacts MUST be immutable once written; updates require a new artifact with a distinct `run_id`.

## 6. Compliance Rules
An implementation is TraceCore v0.1 compliant if and only if it:
1. Executes episodes according to the lifecycle defined above.
2. Enforces budgets strictly—no action may execute once any budget reaches zero.
3. Emits artifacts that validate against `artifact-schema-v0.1.json`.
4. Records deterministic identifiers (`task_hash`, `agent_hash` when available, `spec_version`).
5. Declares determinism guarantees per `/spec/determinism.md`.
6. Provides a compliance flag or mode (`--strict-spec`) that validates artifacts before reporting success.
7. Documents any optional extensions; extensions MUST NOT alter required fields or semantics.

See `/spec/compliance-checklist-v0.1.md` for an auditable checklist.

## 7. Non-Goals
- Defining agent cognition strategies, prompt templates, or reasoning stacks.
- Mandating a particular programming language or framework for runtimes.
- Providing probabilistic or "best effort" determinism grades.
- Allowing mutable or partial artifacts.

## 8. Versioning Policy
1. The spec uses independent semantic versioning (`MAJOR.MINOR.PATCH`).
   - `MAJOR` increments for breaking changes to artifacts, lifecycle, or compliance rules.
   - `MINOR` increments for additive requirements or optional extensions.
   - `PATCH` increments for errata that do not change behavior.
2. Runtime/package versions (e.g., `tracecore 0.9.3`) SHALL declare the spec version they implement (e.g., `tracecore-spec 0.1`). These numbers are intentionally decoupled.
3. Any runtime claiming compliance MUST embed `spec_version` in every artifact and expose it via CLI/API metadata.
4. New spec versions MUST ship updated schema, checklist, and determinism documents within `/spec/`.
