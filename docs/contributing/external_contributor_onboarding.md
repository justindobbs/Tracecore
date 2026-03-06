# External Contributor Onboarding

This guide is the quickest path for contributing to TraceCore if you want to add a task, ship an agent, or prepare a plugin package. It complements the task and agent reference docs by focusing on contribution flow, validation expectations, and review readiness.

## What you can contribute

- **Tasks** — deterministic scenarios under `tasks/` with manifests, setup, actions, validators, registry entries, and spec-freeze updates when applicable.
- **Agents** — reference or framework-backed agents under `agent_bench/agents/` that implement the TraceCore agent interface and respect deterministic budgets.
- **Plugins** — external packages or extension points that integrate with TraceCore task/agent workflows while remaining reproducible and lintable.
- **Docs and examples** — tutorials, onboarding material, CI workflows, and integration guides that improve adoption without changing runtime behavior.

## Start with the right reference doc

Choose the path that matches your contribution:

- **New task or task update** — read [`docs/tasks/plugin_contribution_guide.md`](../tasks/plugin_contribution_guide.md), [`docs/tasks/task_harness.md`](../tasks/task_harness.md), and [`SPEC_FREEZE.md`](../../SPEC_FREEZE.md).
- **New agent** — read [`docs/agents/agents.md`](../agents/agents.md) and [`docs/agents/agent_interface.md`](../agents/agent_interface.md).
- **CLI/runtime or spec-adjacent work** — read [`docs/cli/commands.md`](../cli/commands.md), [`docs/reference/architecture.md`](../reference/architecture.md), and the canonical spec bundle under `spec/`.
- **Integrations/tutorials** — read the relevant tutorial under `docs/tutorials/` and align examples with the current CLI/runtime behavior.

## Contribution expectations

TraceCore prioritizes determinism, auditability, and repeatable validation over benchmark hype. Contributions should preserve these invariants:

- **Deterministic behavior first** — frozen inputs should reproduce identical outcomes under the same task, agent, seed, and budgets.
- **Stable contracts** — changes to task behavior, public CLI surfaces, or artifact schemas need explicit versioning and matching docs.
- **Structured failures** — error paths should use existing runner/task conventions so failures remain debuggable.
- **Reviewable scope** — prefer changes that clearly state what changed, why it changed, and how it was verified.

## Task contributions

When adding or changing a task:

1. Create or update the task directory under `tasks/`.
2. Keep the manifest, `setup.py`, `actions.py`, and `validate.py` aligned.
3. Register the task in `tasks/registry.json`.
4. Update `SPEC_FREEZE.md` if the task becomes part of the frozen benchmark surface.
5. Add or update regression tests that prove the validator and action surface still work.
6. Run local validation before opening a PR.

Minimum validation loop:

```bash
python -m pytest
python -m ruff check agent_bench
tracecore tasks validate --registry
tracecore run --agent agents/toy_agent.py --task your_task@1 --seed 0 --strict-spec
```

If the task introduces a new scenario family, also update the task catalog in `docs/tasks/tasks.md` so contributors and evaluators can discover it.

## Agent contributions

When contributing an agent:

1. Implement the TraceCore loop (`reset`, `observe`, `act`) cleanly.
2. Keep local state explicit and deterministic.
3. Respect task budgets and avoid infinite retry loops.
4. Add targeted tests for the agent’s logic and expected success/failure behavior.
5. Document the agent in `docs/agents/agents.md` if it is intended to be a maintained reference agent.

Useful checks:

```bash
python -m pytest
python -m ruff check agent_bench
```

Additional targeted tests are encouraged for:

- Unit tests for new agent logic
- Integration tests for agent-to-agent communication
- Performance tests for agent coordination

## Plugin contributions

For plugin-style work, use the task/plugin contribution guide as the primary contract reference. In addition:

- Keep plugin APIs additive where possible.
- Make entry points explicit and easy to lint.
- Avoid hidden network or filesystem assumptions outside the declared sandbox/config surface.
- Document installation, expected environment variables, and any signing/integrity expectations.

If a plugin changes the benchmark surface or external onboarding flow, update the relevant docs and mention the operational impact in your PR summary.

## Pull request readiness

Before opening a PR, make sure you can answer these clearly:

- What problem does this change solve?
- What are the major implementation changes?
- How was it validated locally?
- Which docs/spec/checklist files changed alongside the code?

The repo PR template includes the standard checks:

- `python -m pytest`
- `python -m ruff check agent_bench`
- Additional targeted tests as needed
- Spec/docs updates when behavior changes
- Registry + `SPEC_FREEZE.md` updates for new benchmark tasks
- Security/privacy review if touching telemetry, signing, or bundles
- CI verification once pushed

## Review prompts for contributors

Including answers to these in the PR description makes review much faster:

- **Determinism:** Does this change alter frozen task behavior or artifact semantics?
- **Compatibility:** Does any public surface need versioning, migration notes, or new docs?
- **Observability:** If the change fails in CI, what evidence will help maintainers diagnose it quickly?
- **Scope control:** What is intentionally deferred or left unchanged?

## Community feedback loops

If you are unsure about direction before opening a PR:

- Start a GitHub Discussion for workflow, UX, or roadmap questions.
- Open a draft PR early if you want implementation feedback on contracts or naming.
- Link the relevant roadmap/Phase 6 item when proposing work that affects benchmark direction.

Good discussion topics include:

- CLI workflow friction
- New deterministic task ideas
- Multi-agent orchestration patterns
- Telemetry and replay UX expectations
- External integration priorities

## When to update docs and checklists

Update docs whenever behavior, contribution flow, or public expectations change. In practice this usually means touching one or more of:

- `README.md`
- `SPEC_FREEZE.md`
- `docs/tasks/tasks.md`
- `docs/agents/agents.md`
- `docs/reference/architecture.md`
- `tracecore-prd/checklists/phase6.md` when the work maps to the active PRD

## Suggested first contributions

If you are new to the project, good first contributions include:

- Add documentation clarifying a confusing workflow
- Add regression coverage for a task or runner edge case
- Add a deterministic task variant with strong validator coverage
- Improve an existing reference agent or tutorial
- Propose a GitHub Discussion summarizing user friction or adoption feedback
