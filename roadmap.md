# TraceCore roadmap (to v1.0)
This roadmap prioritizes deterministic core stability, auditability, and adoption scaffolding before optional attestations and ecosystem extras.

## Principles
- Deterministic first: stable runner contracts (CLI + artifact schema), frozen task manifests, reproducible baselines.
- Auditability with restraint: integrity hashing now; signatures/attestations once schemas are stable.
- Adoption-focused: CI-ready templates, minimal-start examples, small deterministic task library with clear budgets.
- Scope discipline: optionalize heavy ledger/blockchain and certifications; gate multi-agent/async behind proven single-agent determinism.

## Phases
### Phase 1 (0–1 quarter): Deterministic core + audit hardening
- Freeze runner contracts (CLI + artifact schema); ship deterministic baseline export/compare; shared local/CI TOML.
- IO audit diffs in Trace Viewer; taxonomy regression tests for validator outcomes.
- Artifact integrity via hashed bundles; defer signing until schemas stabilize.
- Security review of GuardedEnv and validator normalization; publish findings.

### Phase 2 (1–2 quarters): Adoption scaffolding + task/library growth
- Expand deterministic task catalog with frozen manifests; publish CI policy templates and “minimal start” examples.
- Integrations: focused adapters for priority stacks (LangChain, OpenAI/Anthropic APIs), with deterministic shims and budget enforcement.
- Structured traces: standardized export (e.g., OTLP) and episode config schema for swapping models/tools under budgets.

### Phase 3 (2–3 quarters): Trust model + ecosystem scale
- Formalize frozen task/version policy, evidence bundles, and contributor playbook.
- Enable optional signing/attestation (e.g., Cosign) once schemas are stable; keep blockchain/IPFS storage as opt-in showcase only.
- Trace diff CLI (tracecore diff run1 run2) and richer failure taxonomy UX.

### Phase 4 (3–4 quarters): Scale and readiness for v1.0
- Performance: parallel episode execution under bounded resources; resource/budget monitoring.
- Reliability: red-team tool-call standardization; regression suites; steady minor release cadence toward v1.0.
- Metrics: CI pilot adoption, reproducibility pass rates, time-to-diagnose regressions.

## Decisions on prior open questions
- P0 focus: contract freeze + deterministic compare flow remains top priority.
- Signing/attestation: optional after schema stability; not mandatory for baseline use.
- Framework/provider priority: start with LangChain and OpenAI/Anthropic APIs before expanding to others (e.g., CrewAI) as demand warrants.
