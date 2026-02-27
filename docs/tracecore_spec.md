---
description: TraceCore technical specification
---

# TraceCore Technical Specification

TraceCore is defined by a **Deterministic Episode Runtime** (see [`core.md`](core.md)) and a set of enforceable contracts that make every run reproducible, auditable, and actionable. This document ties those contracts together as the authoritative technical spec for the product.

## Purpose and scope

This spec describes how TraceCore structures agent episodes, tasks, artifacts, and release governance. It exists so that:

1. Maintainers can evolve the system without violating determinism guarantees.
2. Integrators (agent authors, platform teams) understand the exact surface they must satisfy.
3. External stakeholders can audit TraceCore outputs as trustworthy evidence instead of informal demos.

The spec covers the runtime primitive, runner/harness responsibilities, task packaging, agent expectations, artifact schemas, and release controls. Operational docs (CLI usage, troubleshooting) live elsewhere; this file focuses on the invariant technical core.

## Relationship to the Deterministic Episode Runtime

[`core.md`](core.md) provides the canonical definition of the Deterministic Episode Runtime (DER): inputs (`agent`, `task`, `seed`, `budgets`, `runtime identity`) map deterministically to outputs (trace + verdict + replay artifact).

This technical spec shows how the DER manifests across the TraceCore surfaces:

- **Runner** enforces budgets, sandbox rules, and the termination taxonomy.
- **Task harness** provides deterministic environments plus validators.
- **Agents** implement the reset/observe/act loop against the harness contract.
- **Artifacts** and **ledger** encode the DER’s outputs for CI, dashboards, and trust evidence.

At a glance, every episode follows the same simple path:

1. Lock inputs (`agent`, `task`, `seed`, budgets, version identity).
2. Run the bounded observe -> act -> execute -> validate loop.
3. Terminate with structured outcome fields (`termination_reason`, `failure_type`).
4. Persist replayable artifacts for auditing, CI gating, and baseline comparison.

## Execution lifecycle

Each TraceCore episode MUST follow the lifecycle below:

1. **Resolve identities** — Select `agent_ref`, `task_ref`, harness version, and `seed`. Configuration is frozen before execution.
2. **Load deterministic task** — `task.toml` defines budgets, sandbox allowlists, entrypoints. Hashes are logged to the artifact for replay.
3. **Initialize agent** — Agent receives the task spec and budgets via the reference interface ([`agent_interface.md`](agent_interface.md)).
4. **Loop** while budgets remain:
   - Harness creates an observation snapshot.
   - Agent returns an action payload.
   - Harness executes the action inside the GuardedEnv, records IO audits, and updates budgets.
   - Validator (inline or deferred) ingests task state to detect terminal conditions.
5. **Terminate** — Runner emits `termination_reason` (exact stop) and `failure_type` (analysis bucket) per [`core.md`](core.md).
6. **Persist artifact** — Full trace, metadata, validator outcome, and hashes are written to `.agent_bench/runs/<run_id>.json`. Optional baseline bundles extend this evidence without altering the canonical artifact.

Any deviation (e.g., dynamic budget changes, mutable task manifests, missing validator payloads) violates the spec and must be treated as a bug.

## Contracts by surface

### Runner & harness
- Implements GuardedEnv (filesystem/network allowlists) and enforces `steps`, `tool_calls`, and optional wall-clock budgets.
- Emits structured budgets usage (`steps_used`, `tool_calls_used`, deltas per step) and IO audits per action.
- Maps raw stop reasons to the canonical taxonomy (`budget_exhausted`, `invalid_action`, `sandbox_violation`, `logic_failure`, `timeout`, reserved `non_termination`).
- Provides deterministic replay hooks (`--record`, `--replay-bundle`, baseline comparisons) without hidden state.

### Tasks
- Packaged as deterministic modules (`setup.py`, `actions.py`, `validate.py`, `task.toml`).
- Manifest requirements and registry alignment are defined in [`task_manifest.md`](task_manifest.md) and enforced via `agent-bench tasks validate`.
- Validators must return `{ "ok": bool, "terminal": bool, "details": {…} }` payloads so the runner can emit precise `termination_reason`s and include validator context in artifacts.
- Updating behavior requires bumping the `version` field, updating `SPEC_FREEZE.md`, and re-recording trust evidence.

### Agents
- Must implement the reference API in [`agent_interface.md`](agent_interface.md): `reset(task_spec)`, `act(observation) -> action`, and optional tool helpers.
- Agents are sandbox-agnostic; they operate on the observation payloads and may not access OS resources outside the GuardedEnv policies exposed via task manifests.
- Determinism requirement: given identical inputs and seeds, the agent must produce the same sequence of actions. Nondeterministic policies must be seeded explicitly.

### Artifacts & baselines
- The canonical artifact schema is detailed in [`trace_artifacts.md`](trace_artifacts.md); baseline bundles are add-on evidence defined in [`record_mode.md`](record_mode.md).
- Every artifact entry includes `action_trace`, validator payloads, IO audit trails, and identity metadata (agent, task, seed, harness version, git SHA when available).
- Additive schema evolution is allowed; removals or renames require a major contract bump and changelog entry.

### Ledger & release governance
- Frozen tasks and trust evidence requirements live in [`SPEC_FREEZE.md`](../SPEC_FREEZE.md).
- Release procedures ([`release_process.md`](release_process.md)) ensure contract changes are versioned, artifacts are archived, and ledger entries remain auditable.
- Tests (`tests/test_contract_doc.py`, `tests/test_runner_contract.py`) guard the spec by asserting schema and behavior invariants.

## Determinism guarantees

1. **Input immutability** — Task manifests, agent code, budgets, and seeds are read-only once execution begins.
2. **Bounded interaction** — Budgets guarantee termination; unbounded loops are flagged as `non_termination` once implemented.
3. **Replay fidelity** — Re-running with identical inputs produces equivalent trace/outcome semantics under the same contract, or an explicit, inspectable diff (for example: schema mismatch or harness version mismatch).
4. **Evidence completeness** — Artifacts log every observation/action pair with timestamps, budget deltas, and validator context so operators can reconstruct behavior without auxiliary logs.

## Extension pathways

- **Plugin tasks** expose `agent_bench.tasks` entry points. They must satisfy the same manifest + validator contracts and declare their own spec freeze when shipped externally.
- **Custom agents** can wrap additional tooling but must surface all tool effects through TraceCore actions so the traces remain complete.
- **Dashboards / APIs** read the same artifacts; no privileged APIs bypass the spec. This keeps UI features honest reflections of the DER.

## Unique differentiators within the agent ecosystem

TraceCore’s spec is intentionally opinionated:

1. **Spec-first, product-second** — The DER is the product. CLIs, dashboards, and plugins are thin layers over the same primitive, preventing divergence between “demo” and “real” behaviors.
2. **Artifact-first trust** — Every conclusion comes with a replayable `.json` artifact and optional baseline bundle, making TraceCore closer to CI evidence than leaderboard vibes.
3. **Deterministic sandboxes** — Tasks ship their own GuardedEnv policies and budgets, so agents are judged on disciplined tool use, not luck of an external API.
4. **Failure taxonomy baked in** — `termination_reason` vs. `failure_type` keeps root-cause data consistent across suites, enabling regression gating in real CI systems.
5. **Governed evolution** — SPEC freeze tables, release checklists, and schema tests force additive change. Teams can rely on TraceCore without fearing silent contract drift.

These properties make TraceCore a foundational layer for serious agent evaluation rather than a throwaway benchmark.
