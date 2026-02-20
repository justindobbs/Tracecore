# TraceCore Ledger

The **Ledger** is a static registry of known agents and their baseline performance metrics across the bundled task suite. It provides a quick reference for what agents exist, which tasks they target, and what success rates have been observed.

## CLI

```
agent-bench ledger                    # list all registered agents
agent-bench ledger --show <AGENT>     # show full entry for one agent
```

`<AGENT>` accepts either the full path (e.g., `agents/toy_agent.py`) or the stem (e.g., `toy_agent`).

### Example output

```
$ agent-bench ledger
agents/chain_agent.py  [api]  rate_limited_chain@1, deterministic_rate_service@1
agents/log_stream_monitor_agent.py  [operations]  log_stream_monitor@1
agents/ops_triage_agent.py  [operations]  log_alert_triage@1, config_drift_remediation@1, incident_recovery_chain@1
agents/planner_agent.py  [core]  filesystem_hidden_config@1, rate_limited_api@1, ...
agents/rate_limit_agent.py  [api]  rate_limited_api@1, rate_limited_chain@1
agents/toy_agent.py  [core]  filesystem_hidden_config@1, rate_limited_api@1
```

```
$ agent-bench ledger --show toy_agent
{
  "agent": "agents/toy_agent.py",
  "description": "Minimal deterministic toy agent used for harness validation.",
  "suite": "core",
  "tasks": [
    { "task_ref": "filesystem_hidden_config@1", "success_rate": 1.0, "avg_steps": 4.0 },
    { "task_ref": "rate_limited_api@1",         "success_rate": 0.0, "avg_steps": 1.0 }
  ]
}
```

## Registry format

The registry lives at `agent_bench/ledger/registry.json`. Each entry has:

| Field | Type | Description |
|---|---|---|
| `agent` | string | Relative path to the agent module |
| `description` | string | Short human-readable description |
| `suite` | string | Logical grouping (`core`, `api`, `operations`, `openclaw`) |
| `tasks` | array | Per-task baseline rows (see below) |

Each task row:

| Field | Type | Description |
|---|---|---|
| `task_ref` | string | Task reference in `<id>@<version>` format |
| `success_rate` | float | Fraction of runs that succeeded (0.0–1.0) |
| `avg_steps` | float | Average steps used across recorded runs |

## Python API

```python
from agent_bench.ledger import list_entries, get_entry, iter_entries

# All entries sorted by agent name
entries = list_entries()

# Single entry by path or stem
entry = get_entry("toy_agent")

# Filtered iteration
for entry in iter_entries(suite="api"):
    print(entry["agent"])
```

## Relationship to baselines

The Ledger is a **static snapshot** — it is not updated automatically by `agent-bench run`. For live aggregate stats computed from persisted run artifacts, use `agent-bench baseline`. The Ledger is intended as a stable reference point for CI comparisons and documentation.
