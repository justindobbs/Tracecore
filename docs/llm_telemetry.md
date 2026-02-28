# LLM telemetry

TraceCore agents can emit structured telemetry for LLM calls (shim or provider) using Pydantic models. The telemetry is attached to each action trace entry as `llm_trace` when available.

## What gets recorded
- Provider + model (e.g., OpenAI, Gemini) and whether a deterministic shim was used
- Rendered prompt text
- Completion payload (as JSON string) and success/error flag
- Call/tokens counters (if provided by the shim/provider)
- Timestamp

## Where it appears
- `action_trace[*].llm_trace` in run artifacts produced by the runner
- Generated LangChain adapters include a `llm_trace` buffer and record each call via `LLMCallTelemetry`

## How to consume
- Inspect run artifacts (JSON) to review LLM prompts/responses alongside actions and IO audit
- For CI/debug logs, print or export `llm_trace` as needed (future flag can toggle emission/logging)

## Notes
- Shimmed calls are preferred in CI to keep tests deterministic; telemetry still records provider/model for traceability.
- Budget enforcement is unchanged; telemetry is additive and does not alter behavior.

## Examples

### Sample `llm_trace` entry in a run artifact
```json
"llm_trace": [
  {
    "request": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "prompt": "...rendered prompt...",
      "shim_used": true,
      "metadata": null
    },
    "response": {
      "provider": "openai",
      "model": "gpt-4o-mini",
      "shim_used": true,
      "completion": "{\"type\": \"noop\", \"args\": {}}",
      "success": true,
      "error": null,
      "calls_used": null,
      "tokens_used": null,
      "timestamp": "2026-02-27T23:42:00.000000"
    }
  }
]
```

### Example agent using LLM calls (AutoGen adapter)
Generate the AutoGen adapter agent and run a task; the emitted artifact will include `llm_trace` for each LLM call (shimmed or provider-backed):

```bash
# Generate the agent
python examples/autogen_adapter_demo/generate_autogen_agent.py

# Run against rate_limited_api@1
agent-bench run --agent agents/autogen_rate_limit_agent.py --task rate_limited_api@1 --seed 42

# Inspect llm_trace in the latest run artifact

# Shortcut: built-in inspector (defaults to latest run)
agent-bench inspect

# Inspect a specific artifact
agent-bench inspect --run .agent_bench/runs/<run_id>.json
```

### Disable telemetry in artifacts (env flag)
Set `AGENT_BENCH_DISABLE_LLM_TRACE=1` (or `true/yes`) to omit `llm_trace` from `action_trace` entries if you want leaner artifacts.
