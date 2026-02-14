---
description: Task catalog and significance
---

# Task Catalog

Use this catalog to understand what each bundled task measures, how it is wired, and why it matters to Agent Bench. Every task entry links to its source directory for deeper implementation notes.

## Registry & plugin workflow

- `tasks/registry.json` is the manifest that keeps README/SPEC_FREEZE/docs in sync. When you add or bump a bundled task, update this file so downstream tooling can discover it.
- External task packages can register via the `agent_bench.tasks` entry-point group. See [`docs/task_plugin_template.md`](task_plugin_template.md) for a starter layout, entry-point snippet, and `register()` helper contract.
- The loader merges bundled manifest rows + plugin descriptors, so `agent-bench run --task your_plugin_task@1` works once the plugin package is installed.

## filesystem_hidden_config@1
- **Suite**: filesystem · **Deterministic**: ✅ · **Path**: [`tasks/filesystem_hidden_config/`](../tasks/filesystem_hidden_config/)
- **Core idea**: forces agents to plan cautious filesystem exploration to recover `API_KEY` without brute-force traversal.
- **Skills stressed**:
  - Stateful search across nested directories.
  - Budget-aware exploration vs. repeated reads.
  - Validating when a clue (config file) resolves the goal.
- **Why it matters**: mirrors classic "find config secret" incidents where LLM agents must persist state, avoid loops, and stop once the secret is located.

## rate_limited_api@1
- **Suite**: api · **Deterministic**: ✅ · **Path**: [`tasks/rate_limited_api/`](../tasks/rate_limited_api/)
- **Core idea**: single-endpoint API that enforces strict quotas and transient failures; agents must respect `retry_after` windows.
- **Skills stressed**:
  - Differentiating `rate_limited` vs. `temporary_failure` vs. fatal errors.
  - Implementing exponential/backoff-style waiting with the `wait` action.
  - Submitting the token through `set_output` only when confirmed.
- **Why it matters**: probes whether an agent can follow API etiquette under pressure—no handshake yet, but lots of budget management.

## rate_limited_chain@1
- **Suite**: api · **Deterministic**: ✅ · **Path**: [`tasks/rate_limited_chain/`](../tasks/rate_limited_chain/)
- **Core idea**: extends the previous API with a handshake template and chained endpoints that expire; combines instruction following with rate limits.
- **Skills stressed**:
  - Parsing README/templates to craft the handshake response.
  - Tracking `handshake_id` lifetimes and retry windows simultaneously.
  - Differentiating fatal vs. transient API responses to know when to restart.
- **Why it matters**: captures real-world auth flows (OAuth/device codes) where skipping handshake logic bricks the session.

## deterministic_rate_service@1
- **Suite**: api · **Deterministic**: ✅ · **Path**: [`tasks/deterministic_rate_service/`](../tasks/deterministic_rate_service/)
- **Core idea**: deterministic yet unforgiving service combining handshake confirmation, required payload templates, rate limiting, and a guaranteed transient hiccup.
- **Skills stressed**:
  - Maintaining service state (virtual clock, retry budget, history).
  - Distinguishing `rate_limited`, `temporary_failure`, `bad_request`, `invalid_handshake`, and escalating appropriately.
  - Recovering from fatal payload errors by restarting the flow automatically.
- **Why it matters**: this is Agent Bench’s "depth" scenario—agents must orchestrate multi-step APIs without over-spending limited tool calls, which is representative of production integration incidents.

---
**Next steps**: For full implementation details, open each task’s README (kept alongside the code) or read `docs/task_harness.md` for the harness contract.
