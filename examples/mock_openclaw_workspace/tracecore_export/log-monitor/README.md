# TraceCore Export: log-monitor

Certified TraceCore adapter bundle for OpenClaw agent `log-monitor`.

## Certification

| Field | Value |
|---|---|
| Agent ID | `log-monitor` |
| Task | `log_alert_triage@1` |
| Seed | `0` |
| Harness version | `0.4.1` |
| Run ID | `56649e102fec48baa3713e741932acc0` |
| Certified at | `2026-02-19T02:36:10.636330+00:00` |

## Usage

```bash
# Self-contained adapter (no gateway required)
agent-bench run --agent log-monitor_adapter_agent.py --task log_alert_triage@1 --seed 0

# Gateway-wired adapter (requires running OpenClaw gateway)
# Edit log-monitor_gateway_adapter_agent.py to pass your gateway client, then:
agent-bench run --agent log-monitor_gateway_adapter_agent.py --task log_alert_triage@1 --seed 0
```

## Files

- `log-monitor_adapter_agent.py` — self-contained adapter, tested and certified
- `log-monitor_gateway_adapter_agent.py` — gateway-wired adapter for production use
- `AGENTS.md` — original OpenClaw prompt file
- `openclaw.json` — original OpenClaw agent config
- `manifest.json` — certification metadata
