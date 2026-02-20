# OpenClaw + TraceCore Quickstart

Get your OpenClaw agent running on TraceCore's deterministic harness in under 5 minutes.
No OpenClaw install required to try it out.

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

## 3. Implement `act()` — AI IDE shortcut

If you're in Windsurf, Cursor, or another AI IDE, paste this prompt:

> "Read `tracecore_adapters/log-monitor_adapter_agent.py`, `workspace/AGENTS.md`, and
> `cron/jobs.json`. Implement `act()` so the agent passes `log_alert_triage@1`.
> Run `agent-bench openclaw --agent-id log-monitor --task log_alert_triage@1 --seed 0`
> and fix failures until it passes."

This is the same red-green loop as pytest — the AI reads `failure_type` from
the trace, rewrites `act()`, and re-runs until green.

## 4. Run the test

```bash
agent-bench openclaw --agent-id log-monitor --task log_alert_triage@1 --seed 0
```

## 5. Export a certified bundle

Once it passes:

```bash
agent-bench openclaw-export --agent-id log-monitor
# → tracecore_export/log-monitor/  (inside your openclaw workspace dir)
```

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

To also scaffold a gateway-wired adapter (requires a live OpenClaw gateway):

```bash
agent-bench openclaw --agent-id <id> --gateway
```

## Task selection

| If your agent does… | Use this task |
|---|---|
| File search / config lookup | `filesystem_hidden_config@1` |
| API calls with retry / quota | `rate_limited_api@1` |
| Multi-step orchestration | `rate_limited_chain@1` |
| Log triage / alert filtering | `log_alert_triage@1` |
| Streaming log analysis | `log_stream_monitor@1` |
| Unknown | `filesystem_hidden_config@1` |

## Further reading

- Full tutorial: [`tutorials/openclaw_quickstart.md`](tutorials/openclaw_quickstart.md)
- Agent interface contract: [`docs/agent_interface.md`](docs/agent_interface.md)
- Official OpenClaw docs: [docs.openclaw.ai](https://docs.openclaw.ai)
  - [Agent Runtime](https://docs.openclaw.ai/concepts/agent)
  - [Configuration Reference](https://docs.openclaw.ai/gateway/configuration-reference)
