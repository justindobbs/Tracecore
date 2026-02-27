---
description: Wrap an AutoGen team as a TraceCore agent
---

# AutoGen adapter quickstart

This tutorial shows how to generate a TraceCore-compatible agent from a
Microsoft AutoGen team. The goal is to make framework-based agents measurable,
repeatable, and testable inside TraceCore's deterministic harness.

Use this when you want to:
- Keep your AutoGen team definition intact.
- Plug it into TraceCore tasks with minimal glue.
- Prove that agent behavior can be regression-tested like a unit test.

## Requirements

Install the AutoGen dependencies used by the generated agent:

```bash
pip install autogen-agentchat autogen-ext[openai]
```

You also need `tracecore` installed (or a local editable install).

## Generate an AutoGen-backed agent

Create a generator script:

```python
from agent_bench.integrations.autogen_adapter import generate_agent

generate_agent(
    task_ref="rate_limited_api@1",
    model="gpt-4o-mini",
    agents=[
        {"name": "Worker", "system_message": "Execute tools precisely. Output one JSON action then say DONE."},
        {"name": "Supervisor", "system_message": "Review the action. Correct if wrong. Say DONE."},
    ],
    output_path="agents/autogen_rate_limit_agent.py",
)
```

Run it, then execute the agent:

```bash
python path/to/generate_autogen_agent.py
agent-bench run --agent agents/autogen_rate_limit_agent.py --task rate_limited_api@1 --seed 42
```

## Determinism checklist (pytest-for-agents mode)

The generated agent includes a deterministic state machine and an LLM fallback.
For reproducible runs in CI, use the adapter like this:

1. Solve the task in the deterministic rules first.
2. Gate or remove the LLM fallback in `act()` for CI runs.
3. Record a baseline with `agent-bench baseline --agent ... --task ... --export latest`.
4. Compare future runs with `agent-bench baseline --compare run_a run_b`.

This keeps AutoGen teams compatible with TraceCore's "proof of behavior"
artifact flow while still allowing you to iterate on LLM behavior locally.

## Where the adapter lives

- Adapter source: `agent_bench/integrations/autogen_adapter.py`
- Integration notes: `agent_bench/integrations/README.md`

