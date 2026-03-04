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

---

## Trust evidence and signing

On tagged releases, the CI workflow (`release.yml`) signs each baseline bundle and the registry itself using **Ed25519**. Signatures are stored directly in `registry.json` alongside the metrics.

### Provenance fields added at release time

#### Top-level (`registry.json`)

| Field | Description |
|---|---|
| `ledger_sha256` | SHA-256 of the canonical registry JSON (excluding signature fields) |
| `ledger_signature` | Base64-encoded Ed25519 signature over `ledger_sha256` |
| `signed_at` | ISO 8601 UTC timestamp of signing |
| `signing_pubkey_id` | First 16 hex chars of SHA-256 of the public key bytes |

#### Per-task row

| Field | Description |
|---|---|
| `bundle_sha256` | SHA-256 of the zipped baseline bundle for this run |
| `bundle_signature` | Base64-encoded Ed25519 signature over `bundle_sha256` |
| `signed_at` | ISO 8601 UTC timestamp of this row's signing |

The public key is committed to the repository at `agent_bench/ledger/pubkey.pem` and is bundled into the installed package, so consumers can verify signatures without any external key lookup.

### Verify signatures locally

```
agent-bench ledger verify --registry
agent-bench ledger verify --entry toy_agent
agent-bench ledger verify --bundle .agent_bench/baselines/<run_id>
```

### Python API

```python
from agent_bench.ledger.signing import (
    load_public_key_from_file,
    verify_registry_signature,
    verify_bundle_signature,
)
from agent_bench.ledger import _load_registry
from pathlib import Path

pub = load_public_key_from_file()
registry = _load_registry()
print(verify_registry_signature(registry, pub))  # True after a signed release
```

### Signed ledger as release artifact

Each GitHub Release uploads `ledger-registry-<tag>.json` — a snapshot of `registry.json` at the time of the release, including all signatures. This file is the public ledger of trust evidence for that version.
