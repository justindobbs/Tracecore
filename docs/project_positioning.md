# TraceCore (Agent Bench CLI): Positioning, What It Is Not, and Where It Goes Next

## 1) Executive Snapshot

TraceCore is best understood as a **deterministic test runner for agent loops** ("pytest-for-agents"), not a broad capability leaderboard.

For the canonical primitive definition, see [`docs/core.md`](core.md): TraceCore as a **Deterministic Episode Runtime**.

It optimizes for:
- Reproducibility
- Mechanical pass/fail outcomes
- Budget-aware execution
- Sandboxed, constrained action surfaces
- Artifact-first diagnostics

---

## 2) Positioning Matrix (What Is Actually Distinct)

| Dimension | TraceCore | Typical Agent Benchmark Stacks |
| --- | --- | --- |
| Primary objective | Validate operational reliability of agent loops | Measure broad capability/performance across diverse tasks |
| Task model | Closed-world, deterministic tasks with frozen versions | Mixed task styles; often open-ended or externally dependent |
| Validation | Deterministic validators (`validate.py`), no LLM judges | Often blends scripted checks with model/judge scoring |
| Action interface | Structured, explicit action schema with constrained tools | Frequently natural-language-heavy or benchmark-specific adapters |
| Budgeting | First-class steps/tool-call budgets with hard termination | Budget/cost often tracked, not always enforced as hard task semantics |
| Sandbox posture | Explicit anti-cheating and constrained observability model | Varies by benchmark/environment |
| Reproducibility contract | Seed + task version + agent => reproducible artifacts | Reproducibility quality varies by benchmark and infra dependencies |
| Diagnostics | Raw run artifacts + traceability built into runner/UI | Logs and traces exist, but artifact contracts vary by framework |

---

## 3) Capability View (Quick Visual)

### What TraceCore intentionally maximizes

| Property | Priority | Why it matters |
| --- | --- | --- |
| Determinism | High | Enables regression detection and CI confidence |
| Mechanical validation | High | Removes subjective grading ambiguity |
| Operational constraints | High | Tests if an agent can succeed under real limits |
| Extensibility | Medium-High | Small task packages and plugin direction support growth |
| Environment realism | Medium-Low | Focus is signal and repeatability, not simulation fidelity |

### In one line

> TraceCore trades some realism and breadth for **repeatable, auditable agent reliability testing**.

---

## 4) What TraceCore Is Not (Limitations / Non-Goals)

| Limitation / Non-goal | Practical implication |
| --- | --- |
| Not a "who is smartest" general intelligence benchmark | Scores should not be interpreted as broad model intelligence rankings |
| Not optimized for high-fidelity world simulation | Complex real-world messiness may be underrepresented |
| Not creativity/explanation grading | Great narrative outputs do not matter unless task state validates success |
| Early-stage ecosystem and still opinionated | Expect evolving interfaces, smaller task catalog, and changing conventions |
| Narrow by design (operations-first) | Best fit is reliability and runbook-style behavior, not open-ended assistant UX |

---

## 5) Practical Applications (Where It Creates Immediate Value)

| Use case | How TraceCore helps | Example outcome |
| --- | --- | --- |
| CI regression checks for agent releases | Run fixed seeds/tasks and diff artifacts over time | Catch reliability drops before production rollout |
| Vendor/model comparison for operations agents | Evaluate under identical deterministic constraints | Choose model that is stable, not just flashy |
| Safety and failure-mode testing | Force budget exhaustion, invalid actions, and constrained observations | Identify brittle policies and recovery gaps |
| Team-level acceptance criteria | Define pass/fail gates tied to task versions and run artifacts | "Release blocked unless baseline success >= threshold" |
| Debugging planner loops | Inspect per-step traces and budget consumption | Faster root-cause analysis of decision errors |

---

## 6) Future Vision (Project Direction / Roadmap Draft)

TraceCore, the Deterministic Episode Runtime, moves through four phases on the path to v1.0. Each phase calls out concrete deliverables and exit criteria that map directly to the public roadmap.

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

### Priority lane summary
| Priority | Focus | Milestones | Exit criteria |
| --- | --- | --- | --- |
| P0 (Critical) | Deterministic core + baseline hygiene | Lock runner contracts (CLI + artifact schema), release deterministic baseline compare flow, ship shared local/CI TOML config | Reference tasks run reproducibly across local and CI; schema-breaking changes require explicit version bump |
| P1 (High) | Adoption scaffolding | Expand deterministic task catalog, publish CI policy templates, improve trace and failure analysis UX | Teams can adopt a standard gating workflow with artifact diffs and clear failure taxonomy |
| P2 (Medium) | Trust + ecosystem scale | Formalize frozen task/version policy, improve plugin/registry contribution path, document trust/repro evidence model | External contributors can add tasks/plugins under stable contracts; release-to-release comparability is auditable |

### Execution dependencies and risks
| Risk area | Why it matters | Mitigation |
| --- | --- | --- |
| Contract churn in early APIs | Breaks adoption and invalidates historical comparisons | Introduce versioned contracts, deprecation windows, and schema alerts in CI |
| Task growth without quality bar | More tasks can reduce signal if determinism slips | Require deterministic validator checks, frozen manifests, and taxonomy regression gates |
| CI integration friction | Teams may skip adoption if setup is heavy | Provide opinionated templates, minimal-start examples, and turnkey artifact diff scripts |
| Analysis UX lag | Artifact volume can outpace debugging usefulness | Prioritize top failure modes, ship Trace diff CLI, and document taxonomy mapping |

### Metrics and checkpoints
- **Adoption**: count of CI pilots running TraceCore nightly/weekly; goal is ≥5 before v0.9.
- **Determinism**: reproducibility pass rate across frozen tasks; target ≥99% with automated alarm on drift.
- **Budget discipline**: median tool-call budget consumption vs. ceiling per task; provide dashboard slices per release.
- **Time-to-diagnose regressions**: track mean time from failure detection to root cause using Trace diff tooling; target <1 day by Phase 4.
- **Evidence/attestation readiness**: measure percentage of bundles shipped with integrity hashes and optional signatures once Phase 3 unlocks.

---

## 7) Positioning Statement (Suggested)

**TraceCore is a deterministic, budgeted, and auditable test runner for agent control loops.**
It is not trying to be the broadest leaderboard; it is trying to be the most reliable way to answer:

> "Will this agent behave correctly, repeatedly, under constraints?"

---

## 8) Adoption Guidance

If your top question is:
1. **"How capable is this model in general?"** -> pair TraceCore with broader benchmark suites.
2. **"Can this agent be trusted in production-like loops?"** -> use TraceCore as a primary gate.
3. **"Can we reproduce this result next week in CI?"** -> TraceCore should be your baseline harness.

---

**Bottom line (February 2026):** no public benchmark or standard currently documents the exact deterministic, budgeted, sandboxed harness design and positioning that TraceCore targets.
