# OpenAI Assistants Adapter Example

This example shows a deterministic, CI-safe TraceCore adapter pattern for an OpenAI Assistants-style application.

It mirrors the same recommended shape described in `docs/tutorials/openai_agents.md`:

- keep your real OpenAI app/runtime separate
- expose a small TraceCore adapter agent
- provide a deterministic local mode for repeatable evaluation
- validate the emitted artifact with `strict-spec`

## What this example includes

- `agents/fixture_openai_assistants_agent.py` — a deterministic adapter agent that simulates an Assistants-style thread/run workflow
- focused regression tests proving the adapter emits structured `llm_trace`
- a CI-safe pattern that does not require live API credentials

## Run

```bash
tracecore run --agent examples/openai_assistants_adapter/agents/fixture_openai_assistants_agent.py \
              --task filesystem_hidden_config@1 \
              --seed 0

tracecore verify --latest --strict-spec
```

## Why this exists

OpenAI Assistants integrations usually need a local deterministic path before they become useful for regression testing. This example demonstrates the adapter contract and telemetry shape without requiring a hosted OpenAI dependency in CI.
