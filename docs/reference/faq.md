# TraceCore FAQ

## Positioning and philosophy

### What is TraceCore?
TraceCore is a deterministic, budgeted, and auditable test runner for agent control loops. It is designed to answer a narrow but practical question: can an agent repeatedly succeed under constrained conditions with mechanically verifiable outcomes?

For the broader framing, see [`project_positioning.md`](project_positioning.md).

### What is TraceCore not?
TraceCore is not a general intelligence leaderboard, not an LLM-judge benchmark, and not a high-fidelity world simulator. It intentionally favors repeatability, explicit actions, and deterministic validators over open-ended scoring.

### Why not use an LLM judge?
Because judges reward explanations and style as much as outcomes. TraceCore prioritizes scenarios where success can be checked mechanically in task state or outputs.

### Why not benchmark reasoning quality directly?
Reasoning quality can matter, but TraceCore is optimized for operational reliability first: budget discipline, tool correctness, replayability, and failure diagnosis.

### Why not allow free-form natural language actions?
Free-form actions blur capability boundaries and make failures harder to audit. TraceCore prefers explicit action surfaces so tasks remain inspectable and reproducible.

### Why not give unrestricted shell access?
Unrestricted shell access encourages environment-specific hacks and makes benchmark failures harder to interpret. TraceCore instead uses constrained, task-defined action surfaces.

### Why not use real external APIs?
Live APIs change behavior, rate limits, and availability over time. That breaks determinism, so TraceCore prefers frozen or mocked interfaces unless a scenario explicitly controls the variability.

### Why so opinionated?
Because the project is optimizing for a specific use case: reliable, repeatable evaluation of agent loops under constraints. The constraints are part of the product, not incidental limitations.

## Practical usage

### When should I use TraceCore?
Use it when your question is:

- Will this agent behave correctly under task budgets?
- Can I replay this result later in CI?
- Did a code or model change improve or regress reliability?
- Can I audit what happened from artifacts rather than intuition?

### When should I not use TraceCore by itself?
Do not use it alone if your main goal is broad capability ranking, creative generation evaluation, or open-ended assistant UX benchmarking. In those cases, pair TraceCore with broader evaluation suites.

### How realistic are the tasks?
The tasks are realistic in structure and failure mode, but intentionally simplified to preserve determinism and auditability. TraceCore trades some environmental realism for repeatable signal.

### Why are many tasks short?
Shorter tasks make it easier to isolate failure modes, compare runs, and debug regressions. The project can still support deeper scenarios, but they should remain interpretable and mechanically validated.

### Does TraceCore support multi-agent scenarios?
Yes. Phase 6 introduces multi-agent orchestration patterns and multi-role task coverage, while preserving deterministic task contracts.

## Contributor and integration guidance

### How do I add a new task?
Start with the task contribution docs:

- [`../tasks/plugin_contribution_guide.md`](../tasks/plugin_contribution_guide.md)
- [`../tasks/task_harness.md`](../tasks/task_harness.md)
- [`../tasks/tasks.md`](../tasks/tasks.md)
- [`../contributing/external_contributor_onboarding.md`](../contributing/external_contributor_onboarding.md)

### How do I add or adapt an agent?
Use the agent docs:

- [`../agents/agents.md`](../agents/agents.md)
- [`../agents/agent_interface.md`](../agents/agent_interface.md)
- [`../tutorials/autogen_adapter.md`](../tutorials/autogen_adapter.md)

### How do I adapt OpenClaw agents?
Use the OpenClaw quickstart/tutorial path documented in the repo’s tutorial and adapter docs. If that guide expands in Phase 6, prefer the most current version linked from the README and docs index.

### What should I run before opening a PR?
At minimum:

```bash
python -m pytest
python -m ruff check agent_bench
```

Then add any targeted tests required by the change, and update docs/spec/checklist files when behavior changes.

### Where should I ask questions or propose ideas?
Use GitHub Discussions for workflow, UX, roadmap, and contribution questions. Draft PRs are a good fit when you already have a concrete implementation direction and want feedback on contracts or naming.
