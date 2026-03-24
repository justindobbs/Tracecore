# LangChain Adapter Example

This example shows a production-ready LangChain integration pattern for TraceCore using a deterministic fixture-backed adapter, structured `llm_trace` telemetry, and strict-spec verification.

The recommended default path is the fixture-backed agent in `agents/fixture_langchain_agent.py`, which does not require live API credentials and is safe to run in CI.

## Overview

TraceCore requires agents to implement `reset(task_spec)`, `observe(observation)`, and `act() -> dict`. This example shows how to generate and run a LangChain-backed adapter while keeping the evaluation deterministic with a recorded fixture, exposing `llm_trace` in run artifacts, and validating the final artifact with strict-spec checks.

## Setup

```bash
pip install tracecore langchain-core
```

## Run

```bash
# Recommended deterministic example path
tracecore run --agent examples/langchain_adapter/agents/fixture_langchain_agent.py \
              --task filesystem_hidden_config@1 \
              --seed 0

# Verify the emitted artifact against the frozen TraceCore contract
tracecore verify --latest --strict-spec
```

For a live-provider development path, `agents/langchain_agent.py` remains available and can be wired to `OPENAI_API_KEY`, but the fixture-backed adapter is the CI-safe reference flow.

## How it works

1. `agents/fixture_langchain_agent.py` generates a deterministic LangChain adapter using `agent_bench.integrations.langchain_adapter.generate_agent(...)` and a recorded shim fixture from `tests/fixtures/langchain/filesystem_hidden_config.json`.
2. The generated adapter emits `llm_trace` entries using the shared TraceCore telemetry models, so prompts/completions/providers/models appear in the run artifact in the same format as other hosted integrations.
3. The resulting run artifact passes `strict-spec` validation and is exercised in `.github/workflows/langchain-example-ci.yml`.

## Notes

- The fixture-backed adapter uses a fixed seed (`0`) and recorded completions for reproducibility.
- The example targets `filesystem_hidden_config@1` because it is fast, deterministic, and already covered by strict-spec regressions.
- The CI workflow runs the example tests and a strict-spec check over a real fixture-backed run artifact.
- The live-provider adapter is still useful for local experimentation, but the fixture-backed path is the recommended production/CI example.
