# OpenClaw + TraceCore Quickstart

Get your OpenClaw agent running on TraceCore's deterministic harness in under 5 minutes.
No OpenClaw install required to try it out.

This guide now goes beyond the quickstart and walks through the full adapter flow:

- scaffold an adapter from an OpenClaw workspace
- understand which files drive the adapter behavior
- implement and debug `act()` against deterministic TraceCore tasks
- export a certified bundle for replay and comparison
- move from the mock workspace to a real OpenClaw gateway-backed setup

## 1. Install

```bash
pip install -e ".[dev]"
```

## 2. Try it with the mock workspace (no OpenClaw needed)

```bash
cd examples/mock_openclaw_workspace
agent-bench openclaw --agent-id log-monitor
```

This scaffolds `tracecore_adapters/log-monitor_adapter_agent.py`. Open it — the `act()` stub is
ready to fill in.

### What gets generated

The mock workspace demonstrates the minimum files you need to reason about the adapter:

```text
examples/mock_openclaw_workspace/
├── openclaw.json
├── workspace/AGENTS.md
├── cron/jobs.json
├── tracecore_adapters/
│   └── log-monitor_adapter_agent.py
└── tracecore_export/
```

- `openclaw.json` tells TraceCore how to locate the OpenClaw agent definition.
- `workspace/AGENTS.md` captures the agent's system-level operating instructions.
- `cron/jobs.json` gives you concrete domain context to translate into deterministic agent logic.
- `tracecore_adapters/log-monitor_adapter_agent.py` is the adapter you actually implement and test.

### Architecture at a glance

```text
OpenClaw workspace config + prompts
            ↓
agent-bench openclaw
            ↓
generated TraceCore adapter agent
            ↓
TraceCore task harness (`setup.py` / `actions.py` / `validate.py`)
            ↓
run artifact / bundle / diff / replay workflow
```

The key idea is that TraceCore is not executing the full OpenClaw runtime in this mock loop. It is scaffolding a deterministic adapter that mirrors the agent's intended responsibilities so you can test behavior under a frozen harness.

## 3. Implement `act()` — AI IDE shortcut

If you're in Windsurf, Cursor, or another AI IDE, paste this prompt:

> "Read `tracecore_adapters/log-monitor_adapter_agent.py`, `workspace/AGENTS.md`, and
> `cron/jobs.json`. Implement `act()` so the agent passes `log_alert_triage@1`.
> Run `agent-bench openclaw --agent-id log-monitor --task log_alert_triage@1 --seed 0`
> and fix failures until it passes."

This is the same red-green loop as pytest — the AI reads `failure_type` from
the trace, rewrites `act()`, and re-runs until green.

### Code pointers while implementing

When editing the generated adapter, keep these references open:

- `tracecore_adapters/log-monitor_adapter_agent.py` — the actual adapter logic
- `workspace/AGENTS.md` — the agent's operating instructions and task framing
- `cron/jobs.json` — example workload/context data
- `tasks/log_alert_triage/README.md` — human-readable task expectations
- `tasks/log_alert_triage/actions.py` — exact action surface the adapter can call
- `tasks/log_alert_triage/validate.py` — what success and failure actually mean

If the agent keeps failing, inspect the run artifact and compare:

- what the adapter believed from `observation`
- which action it emitted
- what `result` came back from the task harness
- what `failure_type` or validator output ended the run

## 4. Run the test

```bash
agent-bench openclaw --agent-id log-monitor --task log_alert_triage@1 --seed 0
```

### Recommended debug loop

```bash
agent-bench openclaw --agent-id log-monitor --task log_alert_triage@1 --seed 0
agent-bench inspect
agent-bench verify --latest
```

Use this loop until the adapter passes reliably. If the run regresses after an edit, compare the latest run against a known-good baseline or previous artifact to find the earliest divergence.

## 5. Export a certified bundle

Once it passes:

```bash
agent-bench openclaw-export --agent-id log-monitor
# → tracecore_export/log-monitor/  (inside your openclaw workspace dir)
```

Exported bundles are useful for:

- replay verification
- regression comparisons after prompt or adapter changes
- sharing auditable artifacts with collaborators
- feeding future trust-pipeline and ledger workflows

If you want stronger verification after export, follow with the standard TraceCore bundle/verify flow from the repo root.

---

## Using your own OpenClaw agent

```bash
cd ~/.openclaw/workspace          # or wherever your openclaw.json lives
agent-bench openclaw --agent-id <your-agent-id>
```

`detect_openclaw_agent()` supports both config formats:

| Format | Key | Prompt source |
|---|---|---|
| Official (`agents.list`) | `id`, `workspace` | `<workspace>/AGENTS.md` |
| Community runbook (`agents.named`) | agent name key | `systemPromptFile` |

### How TraceCore chooses prompt/config sources

- In the canonical format, TraceCore resolves the workspace from `agents.list[*].workspace` and then reads `AGENTS.md` from that workspace.
- In the community format, it resolves the prompt path from `systemPromptFile`.
- In both cases, the generated adapter is still a TraceCore-side agent implementation that must satisfy deterministic task contracts.

To also scaffold a gateway-wired adapter (requires a live OpenClaw gateway):

```bash
agent-bench openclaw --agent-id <id> --gateway
```

### Mock adapter vs gateway adapter

Use the **mock adapter** path when you want to:

- iterate quickly on deterministic harness behavior
- test task fit without depending on a live model or gateway
- build regression coverage around agent logic

Use the **gateway adapter** path when you want to:

- validate the real OpenClaw execution path
- test the prompt + runtime + tool wiring more directly
- understand how a live deployment behaves under TraceCore constraints

Gateway-backed runs are more realistic, but they are also more operationally complex and less ideal for the tightest deterministic loops.

## Task selection

| If your agent does… | Use this task |
|---|---|
| File search / config lookup | `filesystem_hidden_config@1` |
| API calls with retry / quota | `rate_limited_api@1` |
| Multi-step orchestration | `rate_limited_chain@1` |
| Log triage / alert filtering | `log_alert_triage@1` |
| Streaming log analysis | `log_stream_monitor@1` |
| Unknown | `filesystem_hidden_config@1` |

### Capability-to-task guidance

- Start with `filesystem_hidden_config@1` if you only need to prove the adapter loop works end-to-end.
- Use `log_alert_triage@1` when your agent's core value is interpreting operational text or alerts.
- Use `log_stream_monitor@1` when the OpenClaw agent is designed around polling or stream consumption.
- Move to chain or multi-step tasks only after the simpler deterministic loop is stable.

This progression keeps debugging costs low while you validate the adapter contract.

## Further reading

- Agent interface contract: [`docs/agents/agent_interface.md`](docs/agents/agent_interface.md)
- Agent catalog: [`docs/agents/agents.md`](docs/agents/agents.md)
- CLI command reference: [`docs/cli/commands.md`](docs/cli/commands.md)
- Debugging playbook: [`docs/operations/debugging_playbook.md`](docs/operations/debugging_playbook.md)
- Official OpenClaw docs: [docs.openclaw.ai](https://docs.openclaw.ai)
  - [Agent Runtime](https://docs.openclaw.ai/concepts/agent)
  - [Configuration Reference](https://docs.openclaw.ai/gateway/configuration-reference)
