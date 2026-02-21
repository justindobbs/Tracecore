# Integrations

> **Status: Experimental — not production-ready. APIs and generated output may change without notice.**

This directory contains adapters that bridge third-party agent frameworks into the TraceCore harness. Each adapter generates a TraceCore-compatible agent file (implementing `reset` / `observe` / `act`) from a framework-specific team or agent definition.

---

## `autogen_adapter.py` — AutoGen → TraceCore

Generates a self-contained TraceCore agent file from a [Microsoft AutoGen](https://github.com/microsoft/autogen) team definition.

### What it does

1. **Loads the task's action schema** from the TraceCore task registry (`agent-bench tasks`), so the generated agent always knows exactly which actions and parameters are valid for the target task.
2. **Renders a Python source file** containing:
   - A deterministic state machine in `act()` that handles common patterns without calling the LLM (rate-limit waits, token extraction, `set_output` commit, info-gathering fallback).
   - A `_consult_team()` fallback that runs a short `RoundRobinGroupChat` conversation when the state machine can't determine the next action.
   - A structured step prompt (`_build_prompt()`) that includes task description, available actions with required parameters, last action/result, visible state, and recent history.
3. **Validates LLM output** before returning it — rejects actions with missing required args and falls back to a safe info-gathering action.

### Usage

```python
from agent_bench.integrations.autogen_adapter import generate_agent

generate_agent(
    task_ref="rate_limited_api@1",
    model="gpt-4o",
    agents=[
        {"name": "Worker", "system_message": "Execute tools precisely. Output one JSON action then say DONE."},
        {"name": "Supervisor", "system_message": "Review the action. Correct if wrong. Say DONE."},
    ],
    output_path="agents/my_autogen_agent.py",
)
```

Then run it:

```sh
agent-bench run --agent agents/my_autogen_agent.py --task rate_limited_api@1 --seed 42
```

### Parameters

| Parameter | Default | Description |
|---|---|---|
| `task_ref` | required | Task reference, e.g. `"rate_limited_api@1"` |
| `model` | `"gpt-4o"` | OpenAI model name passed to `OpenAIChatCompletionClient` |
| `agents` | Worker + Supervisor | List of `{"name": str, "system_message": str}` dicts |
| `class_name` | `"AutoGenTeamAgent"` | Name of the generated Python class |
| `max_turns` | `4` | Max conversation turns per step |
| `termination_keyword` | `"DONE"` | Keyword that ends the AutoGen conversation |
| `output_path` | `"agents/autogen_agent.py"` | Where to write the generated file |

### Requirements

The generated agent file requires:

```
autogen-agentchat
autogen-ext[openai]
```

These are **not** included in TraceCore's default dependencies. Install them separately:

```sh
pip install autogen-agentchat autogen-ext[openai]
```

An `OPENAI_API_KEY` environment variable is required at runtime.

### Experimental caveats

- The generated agent has **not been validated for determinism** — it calls an LLM and will produce different traces on each run. Use `--record` only after confirming the task is solvable without the LLM path (i.e., the deterministic state machine handles it end-to-end).
- The `_consult_team()` fallback uses `asyncio.run()` which may conflict with existing event loops (e.g., Jupyter).
- The action extraction regex (`_extract_action`) is heuristic and may misparse complex nested JSON.
- Further integration testing against all frozen tasks is pending.
