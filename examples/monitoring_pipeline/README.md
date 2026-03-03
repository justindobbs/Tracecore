# Monitoring Pipeline Example

This example shows how to ingest TraceCore run artifacts into a Grafana + Prometheus stack via OTLP export.

## Architecture

```
tracecore export otlp <run_id>
    │
    ▼
OTLP JSON (resourceSpans)
    │
    ├─► Grafana Tempo  (trace visualisation, span search)
    ├─► Prometheus     (metrics scrape via OTLP → OTel Collector)
    └─► Grafana        (dashboard: repro rate, budget P50, taxonomy breakdown)
```

## Quick start

### 1. Start the stack

```bash
docker compose -f examples/monitoring_pipeline/docker-compose.yml up -d
```

### 2. Run an episode and export

```bash
tracecore run --agent agents/toy_agent.py --task filesystem_hidden_config@1 --seed 0
RUN_ID=$(tracecore runs list --limit 1 | awk '{print $1}')
tracecore export otlp "$RUN_ID" --output /tmp/trace.json
```

### 3. Send to the OTel Collector

```bash
curl -X POST http://localhost:4318/v1/traces \
  -H "Content-Type: application/json" \
  -d @/tmp/trace.json
```

### 4. Open Grafana

Navigate to http://localhost:3000 (default: admin/admin).
Import the dashboard from `examples/monitoring_pipeline/grafana/tracecore-dashboard.json`.

## Continuous ingest (CI)

Add to your GitHub Actions workflow after each run:

```yaml
- name: Export and push traces to OTLP collector
  run: |
    RUN_ID=$(tracecore runs list --limit 1 | awk '{print $1}')
    tracecore export otlp "$RUN_ID" | \
      curl -s -X POST "$OTLP_ENDPOINT/v1/traces" \
           -H "Content-Type: application/json" \
           -d @-
  env:
    OTLP_ENDPOINT: ${{ secrets.OTLP_ENDPOINT }}
```

## Key OTLP attributes for dashboards

| Attribute | Description |
|-----------|-------------|
| `tracecore.success` | Episode outcome (bool) |
| `tracecore.failure_type` | Failure class (budget_exceeded, logic_failure, …) |
| `tracecore.termination_reason` | Why the episode ended |
| `tracecore.steps_used` | Steps consumed |
| `tracecore.tool_calls_used` | Tool calls consumed |
| `tracecore.task_ref` | Task reference |
| `tracecore.agent` | Agent module path |

Use these as Prometheus label selectors or Grafana query filters.
