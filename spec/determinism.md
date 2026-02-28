# Determinism Requirements (TraceCore Spec v0.1)

This document defines the determinism guarantees required by the TraceCore specification. All runtimes claiming compliance MUST satisfy these rules and document how they enforce them.

## 1. Seeded determinism
- Every episode SHALL accept an explicit `seed` integer.
- Agents MUST derive all pseudo-random behavior from this seed. Direct calls to unseeded RNGs, non-deterministic tool shuffles, or unordered dict iteration are non-compliant.
- The artifact MUST record `determinism.seed` equal to the runtime seed input.

## 2. Replay determinism
- Runtimes SHALL provide a replay pathway (`--replay`, bundles, or equivalent) that re-executes an artifact using the same inputs and produces identical outputs.
- Any divergence SHALL result in a hard failure with classification `failure_type = "non_deterministic"` or an explicit incompatibility message (e.g., schema mismatch).
- Replay tools MUST assert hash equality for task files, agent binaries, and artifacts.

## 3. Tool mocking and isolation
- Tasks SHALL define GuardedEnv policies covering filesystem and network access.
- Any IO outside those allowlists MUST be mocked or blocked. Silent fallbacks to live systems invalidate determinism.
- When mocks are used, their identities SHALL be documented in `determinism.tooling.mocks`.

## 4. Model version pinning
- LLMs or ML models invoked during an episode MUST log provider, model identifier, and shim version.
- Non-pinned models (e.g., "gpt-4 latest") are non-compliant. Use explicit revisions ("gpt-4o-2026-02-15").
- Model metadata SHALL be recorded in `determinism.tooling.models`.

## 5. Clock and timing controls
- Budgets are authoritative. Optional wall-clock timers MUST rely on deterministic limits (monotonic timers) and record the configured threshold in the artifact.
- Timestamps may reference real UTC time but SHALL NOT be used to influence agent decisions (no time-based randomness).

## 6. Non-compliance conditions
An episode SHALL be marked non-compliant if any of the following occur:
1. Action traces diverge between original run and replay with identical inputs.
2. Task manifests or agent code mutate between run and replay.
3. External services (network APIs, local daemons) produce non-deterministic responses without mocks.
4. The runtime injects hidden state (environment variables, caches) that alter behavior between runs.

## 7. Compliance documentation
- Runtimes SHOULD expose `tracecore --determinism-report` (or equivalent) summarizing seed, models, mocks, and replay status.
- CI pipelines SHOULD run record+replay checks before accepting artifacts into ledgers or baselines.
- Determinism posture MUST be referenced in README and release notes whenever behavior changes.
