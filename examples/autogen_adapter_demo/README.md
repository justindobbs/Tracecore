# AutoGen adapter demo

This example generates a TraceCore-compatible agent from an AutoGen team and
runs it against `rate_limited_api@1`.

## Setup

From the repo root:

```bash
pip install -e .[dev]
pip install autogen-agentchat autogen-ext[openai]
```

## Generate the agent

```bash
python examples/autogen_adapter_demo/generate_autogen_agent.py
```

This writes `agents/autogen_rate_limit_agent.py`.

## Run the task

```bash
agent-bench run --agent agents/autogen_rate_limit_agent.py --task rate_limited_api@1 --seed 42
```

## Determinism note

The generated agent contains a deterministic state machine plus an LLM fallback.
For CI or regression checks, disable or gate the LLM fallback and rely on the
deterministic rules only.

