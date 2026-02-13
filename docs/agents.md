---
description: Reference agents and their behaviors
---

# Agent Catalog

Agent Bench ships with a few reference agents meant to illustrate API usage and
serve as baselines. Use this catalog to understand what each agent does, why it
exists, and when to bring your own implementation via `docs/agent_interface.md`.

| Agent | Target task(s) | Highlights | File |
| --- | --- | --- | --- |
| `ToyAgent` | `filesystem_hidden_config@1` | cautious filesystem exploration, basic error handling | [`agents/toy_agent.py`](../agents/toy_agent.py) |
| `RateLimitAgent` | `rate_limited_api@1` | respects `retry_after`, retries transient failures, payload caching | [`agents/rate_limit_agent.py`](../agents/rate_limit_agent.py) |
| `ChainAgent` | `rate_limited_chain@1`, `deterministic_rate_service@1` | handshake orchestration, payload resets, fatal/transient error recovery | [`agents/chain_agent.py`](../agents/chain_agent.py) |

## ToyAgent
- **Scenario**: Filesystem treasure hunt where the agent must extract `API_KEY`.
- **Loop**: Alternates between `list_dir`, `read_file`, `extract_value`, and
  `set_output`, caching `seen_paths` to avoid re-reading files.
- **Error handling**:
  - Retries `rate_limited`/`temporary_failure` after inserting a `wait` action.
  - Marks missing files as seen to prevent loops.
- **Use it for**: Quick verification that the filesystem harness works, or as a
  template for agents that need light-weight state tracking.

## RateLimitAgent
- **Scenario**: Single-endpoint API with quotas and transient failures.
- **Strategies**:
  1. Fetch client config once, cache the payload, and reuse it.
  2. On `rate_limited`, convert `retry_after` into a `wait` action before
     re-calling `/token`.
  3. On `temporary_failure`, retry immediately.
  4. On `bad_request`, invalidate local payload state and start over.
- **Outputs**: Commits `ACCESS_TOKEN` via `set_output` the moment it appears and
  then idles to let the runner finish cleanly.
- **Use it for**: Baseline runs in CI, reproducing rate-limit regressions, or as
  a scaffold for more advanced networked agents.

## ChainAgent
- **Scenario**: Multi-step handshakes with strict budgets (`rate_limited_chain`
  and `deterministic_rate_service`).
- **Key capabilities**:
  - Fetches handshake and payload templates lazily, caches both, and swaps in the
    current `handshake_id` before calling `/handshake_commit`.
  - Distinguishes between transient (`temporary_failure`) vs. fatal (`bad_request`,
    `invalid_handshake`, `handshake_expired`) errors and resets appropriately.
  - Tracks `pending_wait` to honor rate-limit windows and replays `/token` when
    the cooldown expires.
  - Parameterized `output_key` so new tasks can reuse the agent without code
    changes.
- **Use it for**: Exercising depth tasks, verifying new service logic, or as a
  reference when building your own chain-aware agent.

## Bringing your own agent
1. Read `docs/agent_interface.md` for the required methods (`reset`, `observe`,
   `act`).
2. Inspect how the reference agents maintain local state and respect budgets.
3. Start from the agent that most closely resembles your target task and adapt
   its strategy to your own runtime/tooling.

> Reference agents are intentionally conservative—they prioritize clarity over
> leaderboard-topping scores. Feel free to fork them as starting points.
