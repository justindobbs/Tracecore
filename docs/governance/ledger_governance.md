# TraceCore Ledger Governance

This document defines the rules for contributing to, maintaining, and versioning entries in the TraceCore Ledger — the static registry of certified agents and their baseline performance metrics.

## What is a Ledger entry?

A Ledger entry is a structured record that certifies an agent against one or more TraceCore tasks. It includes:
- The agent's path and description
- Which tasks it targets and what suite it belongs to
- Baseline success rates and step counts
- (Optional) The harness version, seed policy, and canonical run artifact IDs

Entries live in `agent_bench/ledger/registry.json` and must conform to `agent_bench/ledger/manifest.schema.json`.

---

## Contributor checklist

Before submitting a new or updated Ledger entry, verify all of the following:

### 1. Agent file exists and is importable
- The `agent` path must be relative to the repository root (e.g., `agents/my_agent.py`).
- The agent must implement `reset(task_spec)`, `observe(observation)`, and `act() -> dict`.
- Run `agent-bench tasks validate --registry` — must exit 0.

### 2. At least one passing run exists
- Run the agent against each listed task:
  ```powershell
  agent-bench run --agent agents/my_agent.py --task <task_ref> --seed 0
  ```
- At least one task must produce `"success": true`.
- Record the `run_id` from the output — it becomes the `run_artifact` field.

### 3. Baseline metrics are accurate
- Compute metrics from actual run artifacts:
  ```powershell
  agent-bench baseline --agent agents/my_agent.py --task <task_ref>
  ```
- Use the reported `success_rate` and `avg_steps` values in your entry.
- Do **not** hand-edit these numbers without corresponding run artifacts.

### 4. Entry conforms to the schema
- Validate your JSON against `agent_bench/ledger/manifest.schema.json` before submitting.
- Required fields: `agent`, `description`, `suite`, `tasks[]` (each with `task_ref`, `success_rate`, `avg_steps`).
- Optional but recommended: `harness_version`, `published_at`, `run_artifact` per task row.

### 5. Tests pass
```powershell
python -m pytest
```

---

## Required metadata (minimum viable entry)

```json
{
  "agent": "agents/my_agent.py",
  "description": "One-sentence description of what this agent does.",
  "suite": "core",
  "tasks": [
    {
      "task_ref": "filesystem_hidden_config@1",
      "success_rate": 1.0,
      "avg_steps": 5.0
    }
  ]
}
```

## Recommended metadata (certified entry)

```json
{
  "agent": "agents/my_agent.py",
  "description": "One-sentence description of what this agent does.",
  "suite": "core",
  "harness_version": "0.6.0",
  "seed_policy": "fixed",
  "published_at": "2026-02-20",
  "maintainer": "your-github-handle",
  "tasks": [
    {
      "task_ref": "filesystem_hidden_config@1",
      "success_rate": 1.0,
      "avg_steps": 5.0,
      "avg_tool_calls": 3.0,
      "run_count": 3,
      "seed": 0,
      "run_artifact": "<32-char run_id hex>"
    }
  ]
}
```

---

## Versioning policy

### When to update an entry
- **Success rate or avg_steps change** after re-running: update the metrics and bump `published_at`.
- **Agent logic changes**: re-run against all listed tasks, update metrics, and note the change in `CHANGELOG.md`.
- **New task added to an agent**: add a new task row; do not remove existing rows unless the task is deprecated.

### When to create a new entry
- A new agent file is added to the repository.
- An OpenClaw adapter is exported and certified.

### When to remove an entry
- The agent file is deleted from the repository.
- The agent is superseded by a newer version with a different path.
- Removal requires a `CHANGELOG.md` entry explaining why.

### Harness version tagging
- Set `harness_version` to the current value in `pyproject.toml` when recording baselines.
- If the harness version changes and behavior is affected, re-run and update the entry.
- Old entries without `harness_version` are treated as pre-certification snapshots.

---

## PR template

When submitting a Ledger entry PR, include the following in your PR description:

```
## Ledger entry: <agent stem>

**Agent path:** agents/my_agent.py
**Suite:** core | api | operations | openclaw
**Tasks covered:** task_ref@version, ...

### Evidence
- [ ] Agent file exists and imports cleanly
- [ ] At least one passing run: run_id = `<hex>`
- [ ] Metrics computed from `agent-bench baseline` output
- [ ] Entry validates against manifest.schema.json
- [ ] `python -m pytest` passes

### Harness version
`0.6.0` (or current)

### Notes
<!-- Any context about the agent's strategy, known limitations, or task-specific behaviour -->
```

---

## Suite definitions

| Suite | Description |
|---|---|
| `core` | General-purpose agents targeting filesystem and foundational tasks |
| `api` | Agents specialised in rate-limited API and handshake choreography |
| `operations` | Agents targeting log triage, config drift, and incident recovery |
| `openclaw` | OpenClaw adapter agents exported via `agent-bench openclaw-export` |

---

## Relationship to trust evidence bundles

Ledger entries are the **human-readable layer** of the trust model. The underlying evidence is:
- Run artifacts in `.agent_bench/runs/` (produced by `agent-bench run`)
- Baseline exports in `.agent_bench/baselines/` (produced by `agent-bench baseline --export`)
- Trust bundles in `deliverables/trust_bundle_vX.Y.Z/` (produced at release time per `docs/release_process.md`)

A Ledger entry's `run_artifact` field links directly to the canonical run artifact that proves the claimed `success_rate`.
