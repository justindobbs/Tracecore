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

For a full walkthrough, see `docs/tutorials/autogen_adapter.md` and the
`examples/autogen_adapter_demo` example.

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

---

## `langchain_adapter.py` — LangChain Runnable → TraceCore (OpenAI / Anthropic)

Generates a TraceCore-compatible agent that wraps a LangChain `ChatPromptTemplate`
and `JsonOutputParser`. Instead of calling LLMs directly, the adapter can load a
**deterministic shim fixture** (see `llm_shims.py`) that replays recorded completions
while enforcing explicit call/token budgets. When no fixture is provided, the
adapter can invoke OpenAI (Responses API) or Anthropic (Messages API) with
temperature forced to zero and tight token ceilings.

### Usage

```python
from agent_bench.integrations.langchain_adapter import generate_agent

generate_agent(
    task_ref="rate_limited_api@1",
    provider="openai",           # or "anthropic"
    model="gpt-4o-mini",
    shim_fixture="fixtures/rate_limit_shim.json",  # optional deterministic responses
    max_calls=4,
    max_tokens=2000,
    output_path="agents/langchain_rate_limit_agent.py",
)
```

### Determinism + budgets

- When `shim_fixture` or `shim_responses` is provided, the generated agent uses
  `DeterministicLLMShim` and rejects any prompt whose key is missing from the
  fixture, guaranteeing reproducible traces.
- `LLMBudget` enforces both LLM call count (`max_calls`) and token ceilings
  (`max_tokens`). Any overrun triggers a `BudgetViolation`, which the adapter
  converts into a safe `wait` action so the harness records a deterministic
  failure instead of crashing.
- Direct OpenAI/Anthropic calls remain opt-in; for baseline recording we expect
  teams to capture fixtures with the included shim utilities.

### Requirements

```
langchain-core>=0.2
```

Optional runtime deps (only when not using shims):

- `openai>=1.0` for OpenAI Responses API access.
- `anthropic>=0.25` for Claude Messages API access.

### Hosted integration tests

Hosted LLM integration coverage lives in `tests/test_hosted_llm_integrations.py`.
These tests are **opt-in** and are skipped by default unless explicitly enabled.

Environment variables:

- `TRACECORE_RUN_HOSTED_TESTS=1` enables real-provider test execution.
- `OPENAI_API_KEY` enables the OpenAI slice.
- `ANTHROPIC_API_KEY` enables the Anthropic slice.
- `TRACECORE_HOSTED_OPENAI_MODEL` optionally overrides the default OpenAI hosted model (`gpt-5-nano`).
- `TRACECORE_HOSTED_ANTHROPIC_MODEL` optionally overrides the default Anthropic hosted model (`claude-3-5-sonnet-latest`).

Example commands:

```powershell
# OpenAI hosted path
$env:TRACECORE_RUN_HOSTED_TESTS="1"
$env:OPENAI_API_KEY="..."
python -m pytest tests/test_hosted_llm_integrations.py -k openai -rs

# Anthropic hosted path
$env:TRACECORE_RUN_HOSTED_TESTS="1"
$env:ANTHROPIC_API_KEY="..."
python -m pytest tests/test_hosted_llm_integrations.py -k anthropic -rs
```

```cmd
REM OpenAI hosted path
set TRACECORE_RUN_HOSTED_TESTS=1
set OPENAI_API_KEY=...
python -m pytest tests/test_hosted_llm_integrations.py -k openai -rs

REM Anthropic hosted path
set TRACECORE_RUN_HOSTED_TESTS=1
set ANTHROPIC_API_KEY=...
python -m pytest tests/test_hosted_llm_integrations.py -k anthropic -rs
```

Notes:

- These tests make **real external API calls** and may incur usage cost.
- OpenAI coverage uses the Responses API path in the generated LangChain adapter.
- The tests are intended for developer verification and focused provider checks, not for default local runs.
- Keep deterministic baseline recording on shim fixtures; do not treat these hosted tests as replay-stable evidence.

---

## `llm_shims.py` — Deterministic LLM fixtures + budgets

Exports three utilities:

| Symbol | Description |
| --- | --- |
| `LLMBudget` | Lightweight call/token counter; raises `BudgetViolation` when a limit is crossed. |
| `DeterministicLLMShim` | Returns recorded completions either via key-value fixtures or FIFO queues. Integrations can pass prompts to `complete()` and receive deterministic strings. |
| `BudgetViolation` | Exception raised for budget overruns, allowing adapters to handle them gracefully. |

Example fixture usage:

```python
from agent_bench.integrations import DeterministicLLMShim, LLMBudget

shim = DeterministicLLMShim.from_fixture(
    "fixtures/filesystem_hidden_config_shim.json",
    budget=LLMBudget(max_calls=3, max_tokens=1500),
)
text = shim.complete("PROMPT", metadata={"response_key": "claude-3"})
```

Fixtures are simple JSON objects mapping `response_key` (or prompt hash) to the
exact completion text. This keeps TraceCore baseline runs deterministic even when
LangChain or other frameworks would normally reach into live LLM APIs.
