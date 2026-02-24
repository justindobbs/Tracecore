# TraceCore roadmap (to v1.0)
TraceCore, the Deterministic Episode Runtime, prioritizes deterministic core stability, auditability, and adoption scaffolding before optional attestations and ecosystem extras.

## Principles
- Deterministic first: stable runner contracts (CLI + artifact schema), frozen task manifests, reproducible baselines.
- Auditability with restraint: integrity hashing now; signatures/attestations once schemas are stable.
- Adoption-focused: CI-ready templates, minimal-start examples, small deterministic task library with clear budgets.
- Scope discipline: optionalize heavy ledger/blockchain and certifications; gate multi-agent/async behind proven single-agent determinism.

## Phases
### Phase 1 (0–1 quarter): Deterministic core + audit hardening
**Deliverables**
- Freeze runner contracts (CLI + artifact schema) and land deterministic baseline export/compare with shared local/CI TOML.
- Ship IO audit diffs in Trace Viewer plus taxonomy regression tests for validator outcomes.
- Enforce artifact integrity via hashed bundles and publish GuardedEnv + validator normalization security review.
**Exit criteria**
- Reference agents can replay frozen tasks reproducibly (local + CI) with zero schema drift.
- Validator taxonomy events are emitted deterministically in regression suites.
- Integrity hashing is on by default with documented verifier steps.

### Phase 2 (1–2 quarters): Adoption scaffolding + task/library growth
**Deliverables**
- Expand deterministic task catalog with frozen manifests, CI policy templates, and “minimal start” examples.
- Ship focused adapters for priority stacks (LangChain, OpenAI/Anthropic APIs) with deterministic shims and budget enforcement.
- Produce structured trace exports (e.g., OTLP) plus an episode config schema for swapping models/tools under budgets.
**Exit criteria**
- Teams can adopt TraceCore via turnkey templates that cover pass/fail gates, artifact diffing, and budget alerts.
- At least three external agents run on the expanded task catalog without contract tweaks.
- OTLP/episode config exports flow into a sample monitoring pipeline without manual patching.

### Phase 3 (2–3 quarters): Trust model + ecosystem scale
**Deliverables**
- Formalize frozen task/version policy, evidence bundles, and contributor playbook.
- Enable optional signing/attestation (e.g., Cosign) once schemas are stable; keep blockchain/IPFS storage opt-in.
- Deliver Trace diff CLI (`tracecore diff run1 run2`) and richer failure taxonomy UX.
**Exit criteria**
- Evidence bundle format is versioned, documented, and consumed by at least one pilot integrator.
- Signing/attestation passes smoke tests for deterministically hashed bundles without blocking unsigned flows.
- Trace diff CLI highlights regression deltas and taxonomy shifts in <10s for baseline scenarios.

### Phase 4 (3–4 quarters): Scale and readiness for v1.0
**Deliverables**
- Performance: parallel episode execution under bounded resources plus resource/budget monitoring.
- Reliability: red-team tool-call standardization, hardened regression suites, and steady minor release cadence toward v1.0.
- Metrics: CI pilot adoption dashboards, reproducibility pass rates, time-to-diagnose regressions instrumentation.
**Exit criteria**
- Parallel runs on bounded hardware show ≤5% nondeterminism rate with back-pressure controls.
- Nightly regression packs cover all frozen tasks with <1% flake rate.
- Metrics dashboards show upward trends for CI adoption and declining MTTR for regressions across two consecutive releases.

## Decisions on prior open questions
- P0 focus: contract freeze + deterministic compare flow remains top priority.
- Signing/attestation: optional after schema stability; not mandatory for baseline use.
- Framework/provider priority: start with LangChain and OpenAI/Anthropic APIs before expanding to others (e.g., CrewAI) as demand warrants.

## Priority lane summary
| Priority | Focus | Milestones | Exit criteria |
| --- | --- | --- | --- |
| P0 (Critical) | Deterministic core + baseline hygiene | Lock runner contracts (CLI + artifact schema), release deterministic baseline compare flow, ship shared local/CI TOML config | Reference tasks run reproducibly across local and CI; schema-breaking changes require explicit version bump |
| P1 (High) | Adoption scaffolding | Expand deterministic task catalog, publish CI policy templates, improve trace and failure analysis UX | Teams can adopt a standard gating workflow with artifact diffs and clear failure taxonomy |
| P2 (Medium) | Trust + ecosystem scale | Formalize frozen task/version policy, improve plugin/registry contribution path, document trust/repro evidence model | External contributors can add tasks/plugins under stable contracts; release-to-release comparability is auditable |

## Execution dependencies and risks
| Risk area | Why it matters | Mitigation |
| --- | --- | --- |
| Contract churn in early APIs | Breaks adoption and invalidates historical comparisons | Introduce versioned contracts, deprecation windows, and schema alerts in CI |
| Task growth without quality bar | More tasks can reduce signal if determinism slips | Require deterministic validator checks, frozen manifests, and taxonomy regression gates |
| CI integration friction | Teams may skip adoption if setup is heavy | Provide opinionated templates, minimal-start examples, and turnkey artifact diff scripts |
| Analysis UX lag | Artifact volume can outpace debugging usefulness | Prioritize top failure modes, ship Trace diff CLI, and document taxonomy mapping |

## Metrics and checkpoints
- **Adoption**: count of CI pilots running TraceCore nightly/weekly; goal is ≥5 before v0.9.
- **Determinism**: reproducibility pass rate across frozen tasks; target ≥99% with automated alarm on drift.
- **Budget discipline**: median tool-call budget consumption vs. ceiling per task; provide dashboard slices per release.
- **Time-to-diagnose regressions**: track mean time from failure detection to root cause using Trace diff tooling; target <1 day by Phase 4.
- **Evidence/attestation readiness**: measure percentage of bundles shipped with integrity hashes and optional signatures once Phase 3 unlocks.
