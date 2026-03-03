# LangChain Adapter Example

This example shows how to wrap a LangChain agent to run inside the TraceCore Deterministic Episode Runtime.

**Note**: This example requires an OpenAI API key to be set in the environment as `OPENAI_API_KEY`.

## Overview

TraceCore requires agents to implement `reset(task_spec)`, `observe(observation)`, and `act() -> dict`. This adapter bridges a LangChain `AgentExecutor` to that interface while keeping the episode deterministic (fixed seed, no streaming side effects outside the guarded environment).

## Setup

```bash
pip install tracecore langchain langchain-openai
export OPENAI_API_KEY=sk-...
```

## Run

```bash
# Using the episode config (model/budget overrides without touching the task)
tracecore run --from-config examples/langchain_adapter/episode.json

# Or directly
tracecore run --agent examples/langchain_adapter/agents/langchain_agent.py \
              --task filesystem_hidden_config@1 \
              --seed 0
```

## How it works

1. `langchain_agent.py` — implements the TraceCore agent interface; `act()` invokes `AgentExecutor.invoke()` with the last observation and maps the output to a TraceCore action dict.
2. `episode.json` — overrides `model`, `budget_override`, and `seed` without modifying the task manifest. Uses `budget_override: {steps, tool_calls}` and `wall_clock_timeout_s` as top-level fields.
3. The adapter captures `llm_trace` (token usage, model name, latency) on `agent.llm_trace` so it appears in the run artifact.

## Notes

- The adapter uses a fixed seed (0) for reproducibility. To change the seed, modify the `seed` field in `episode.json`.
- The adapter uses the `filesystem_hidden_config` task from the TraceCore task library. To use a different task, modify the `task` field in `episode.json`.
- The adapter uses the `openai/gpt-4o` model. To use a different model, modify the `model` field in `episode.json`.
- The adapter does not support streaming or real-time feedback during execution. It only captures the final result and LLM trace.
- The adapter does not handle retries or error recovery beyond what LangChain provides. If the agent fails, the episode ends.
- The adapter does not support custom tool schemas or dynamic tool registration. All tools must be defined in the agent configuration.
