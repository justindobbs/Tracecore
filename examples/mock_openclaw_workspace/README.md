# Mock OpenClaw Workspace

A minimal OpenClaw workspace for testing `agent-bench openclaw` **without
installing OpenClaw**. The agent (`log-monitor`) monitors log streams and
triages alerts by severity — a good match for the built-in `log_alert_triage@1`
and `log_stream_monitor@1` tasks.

## Structure

```
mock_openclaw_workspace/
├── openclaw.json          # canonical agents.list config (official format)
├── workspace/
│   └── AGENTS.md          # agent system prompt (skills, behaviour, constraints)
└── cron/
    └── jobs.json          # two example cron jobs (log scan + rate-limit watchdog)
```

## Try it

From this directory:

```bash
# 1. Scaffold the TraceCore adapter (no OpenClaw install needed)
agent-bench openclaw --agent-id log-monitor

# 2. In your AI IDE, ask:
#    "Read log-monitor_adapter_agent.py, workspace/AGENTS.md, and cron/jobs.json.
#     Implement act() so the agent passes log_alert_triage@1."

# 3. Run the test (red-green loop until it passes)
agent-bench openclaw --agent-id log-monitor --task log_alert_triage@1 --seed 0

# 4. Export the certified bundle
agent-bench openclaw-export --agent-id log-monitor
```

## Why this agent maps well to built-in tasks

| Cron job / skill | Matching TraceCore task |
|---|---|
| Morning log scan — triage ERROR/CRITICAL | `log_alert_triage@1` |
| Streaming log pattern detection | `log_stream_monitor@1` |
| Rate-limit watchdog — 429 retry | `rate_limited_api@1` |

See `tutorials/openclaw_quickstart.md` §9 for the full capability → task table.
