# TraceCore Architecture: Reference Implementation vs. Spec

TraceCore’s source of truth is the specification under `/spec/`. The Python code in this repository implements that specification, but any language or runtime can replicate the same behavior by honoring the same contracts.

## 1. Spec-driven runtime
1. **Inputs frozen by the spec** — `agent_ref`, `task_ref`, `seed`, `budgets`, and `spec_version` are resolved before execution. The runtime loads these values, records them verbatim, and refuses to mutate them mid-episode.
2. **GuardedEnv + task harness** — Tasks declare filesystem/network policies and validators inside `task.toml`. The runtime simply enforces these declarations; new implementations must respect the same manifest contract.
3. **Validator + taxonomy** — Validators emit structured payloads that the runtime maps into the canonical termination taxonomy (`success`, `budget_exhausted`, `logic_failure`, etc.) defined by the spec.
4. **Artifact serializer** — After termination, the runtime serializes the run using `/spec/artifact-schema-v0.1.json`. The schema—not Python internals—is the normative definition of the output format.

## 2. Artifact-first design
```
Agent  ──▶ Runner ──▶ Artifact (.json)
                    ├─▶ Baseline bundle (manifest/tool_calls/validator)
                    └─▶ FastAPI Dashboard & APIs
```
- Artifacts are immutable and portable. CI, dashboards, and external services all read the same JSON.
- Bundles add integrity hashes so third parties can verify provenance without running the CLI.
- Because the schema is language-neutral, another team could build a Rust or TypeScript runner that emits the same format and remain TraceCore-compliant.

## 3. Reference implementation boundaries
| Layer | Reference behavior | Spec requirement |
| --- | --- | --- |
| CLI (`tracecore`, `agent-bench`) | Provides user-friendly commands, convenience flags, dashboard launchers. | Optional. Other runtimes can expose different CLIs if artifacts/spec are satisfied. |
| Runner | Enforces budgets, sandbox rules, validator lifecycle, and emits termination taxonomy. | Required. Any compliant runtime must implement the same lifecycle. |
| Artifact serializer | Uses Pydantic/typing helpers to guarantee schema compliance. | Required output format, implementation details optional. |
| Dashboard / APIs | FastAPI UI driven entirely by stored artifacts. | Optional; showcases how artifacts unlock replay + diffs. |

## 4. Building alternative runtimes
To create a new implementation (e.g., Rust service, JS agent host):
1. Consume `/spec/tracecore-spec-v0.1.md` for lifecycle and compliance rules.
2. Validate artifacts against `/spec/artifact-schema-v0.1.json`.
3. Follow `/spec/determinism.md` for seeded runs, mocks, and model pinning.
4. Use `/spec/compliance-checklist-v0.1.md` to gate releases or CI runs.
5. Publish the runtime identity (name + version) and declared spec version inside every artifact.

If all artifacts validate and the lifecycle is honored, the implementation is considered spec-compliant even if it shares zero code with this repository.

## 5. Compliance tooling
- `tracecore run --strict-spec` validates artifacts post-run against `/spec/artifact-schema-v0.1.json`, checks required metadata (`spec_version`, `runtime_identity`, `task_hash`, `artifact_hash`), and verifies `failure_type` is within the canonical taxonomy. Exits non-zero on any violation.
- Every run artifact now embeds `spec_version`, `runtime_identity`, `task_hash`, `agent_ref`, `budgets`, and `artifact_hash` automatically — compliance checks are additive post-run assertions, not separate execution modes.
- CI workflows can gate merges with `agent-bench run --agent ... --task ... --strict-spec`.
- Future deliverables may include hosted validators that accept artifacts over HTTPS and respond with compliance reports, leveraging `/spec/artifact-schema-v0.1.json` as the portable contract.
