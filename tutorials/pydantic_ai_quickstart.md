# Pydantic-AI Quickstart

This guide shows how to build TraceCore agents using pydantic-ai, a structured agent framework with typed schemas and tool validation.

## Why Pydantic-AI?

- **Type safety**: Observations and actions are validated Pydantic models
- **Tool registry**: Pre-built tools with clear schemas
- **Multi-provider**: Works with OpenAI, Anthropic, local models
- **Deterministic**: Integrates with TraceCore's seeded replay system

## Security Considerations
 
TraceCore sandboxes task environments, but LLM agents still need a few guardrails:
 
1. **Prompt injection** – Task files can contain misleading instructions. Keep your system prompt explicit about ignoring instructions that conflict with the task spec, and review traces when onboarding a new task.
2. **Action schemas** – The harness validates action types/args. If you add custom task actions, keep them side-effect free (no raw shell commands, no host-level file writes) so agents can't escape the sandbox.
3. **API keys** – Treat provider keys as secrets. Environment variables are convenient, but avoid printing them or persisting them in traces; rotate frequently when experimenting.
4. **Local runtimes** – When using Ollama or other local models, run the daemon under a restricted account; TraceCore only guards the agent's sandbox, not the model host.
5. **Traces** – Consider traces untrusted input before piping them into downstream dashboards or tools; sanitize if you plan to share them.
 
Following these practices keeps the deterministic harness intact while minimizing LLM-specific risk.

## Installation

```bash
# Install TraceCore with pydantic-ai support
pip install -e ".[pydantic]"

# Set up your LLM provider (using shell `export`; feel free to use PowerShell `setx`, `.env` files, etc.)
# OpenAI
export OPENAI_API_KEY=your-openai-key

# Anthropic
export ANTHROPIC_API_KEY=your-anthropic-key

# Local via Ollama (no key, but ensure Ollama is running)
# ollama serve
```

## Quick Example

### Option A: Import the bundled agent
Already have a filesystem task and just want to run it? Use the packaged `FilesystemPydanticAgent`:

```python
from agents.pydantic_ai_agent import FilesystemPydanticAgent

agent = FilesystemPydanticAgent()
```

Then run it with:

```bash
agent-bench run --agent agents/pydantic_ai_agent.py --task filesystem_hidden_config@1 --seed 42
```

### Option B: Create your own
If you need a custom prompt/model/tools, copy the reference agent below and tweak as needed:

```python
# agents/my_agent.py
from agent_bench.integrations.pydantic_ai import PydanticAIAgent, filesystem_tools

SYSTEM_PROMPT = """
You are solving filesystem tasks.
Goal: Find and extract the API_KEY from hidden config files.
Tools: list_dir, read_file, extract_value, set_output
"""

class MyAgent(PydanticAIAgent):
    def __init__(self):
        super().__init__(
            model="openai:gpt-4o-mini",
            tools=filesystem_tools,
            system_prompt=SYSTEM_PROMPT,
        )
```

Run your custom agent with the same command but pointing at your file:

```bash
agent-bench run --agent agents/my_agent.py --task filesystem_hidden_config@1 --seed 42
```

## Using Different Models

You choose the provider by passing a different `model` string when you initialize your agent (inside the `super().__init__` call). For example:

```python
class MyAgent(PydanticAIAgent):
    def __init__(self):
        super().__init__(
            model="openai:gpt-4o-mini",  # <-- swap this string to change providers
            tools=filesystem_tools,
            system_prompt=SYSTEM_PROMPT,
        )
```

Supported model strings:

- **OpenAI** – `"openai:gpt-4o-mini"`, `"openai:gpt-4o"`
- **Anthropic** – `"anthropic:claude-3-5-sonnet-20241022"`
- **Local via Ollama** – `"ollama:llama3.2"` (requires an Ollama instance running)

Swap the string, set the matching API key (if required), and the base class routes requests to that provider.

## Available Tools

### Filesystem Tools
For tasks like `filesystem_hidden_config@1`:

```python
from agent_bench.integrations.pydantic_ai import filesystem_tools

# Includes:
# - list_dir(path: str) -> ListDirAction
# - read_file(path: str) -> ReadFileAction
# - extract_value(content: str, key: str) -> ExtractValueAction
# - set_output(key: str, value: str) -> SetOutputAction
```

### API Tools
For tasks like `rate_limited_api@1`:

```python
from agent_bench.integrations.pydantic_ai import api_tools

# Includes:
# - call_api(endpoint: str, payload: dict | None) -> CallApiAction
# - wait(steps: int) -> WaitAction
# - set_output(key: str, value: str) -> SetOutputAction
```

## Importing External Agents

You can use agents defined outside the TraceCore repository—whether a standalone Python file or an installed package.

### Option 1: Absolute file path
Reference the agent file directly:

```bash
agent-bench run --agent /path/to/my_external_agent.py --task filesystem_hidden_config@1 --seed 42
```

Ensure the file exports an `Agent` class (or compatible `reset`/`observe`/`act` methods).

### Option 2: PYTHONPATH
If your agent is part of a local package, add its root to `PYTHONPATH`:

```bash
export PYTHONPATH="/path/to/agent_package:$PYTHONPATH"
agent-bench run --agent my_package.my_agent --task filesystem_hidden_config@1 --seed 42
```

### Option 3: Installed package
Install your agent package (e.g., via pip) so it’s on the default path:

```bash
pip install -e /path/to/my_agent_package
agent-bench run --agent my_agent_package.agent_module --task filesystem_hidden_config@1 --seed 42
```

**Note:** External agents must still implement the TraceCore `Agent` interface (`reset`, `observe`, `act`). See `agent_bench/agent/interface.py` for the contract.

## Custom Tools

Define your own tools for specialized tasks:

```python
from agent_bench.integrations.pydantic_ai.schemas import ActionModel

def my_custom_tool(arg1: str, arg2: int) -> ActionModel:
    # Return a valid action model
    return CustomAction.create(arg1, arg2)

class MyAgent(PydanticAIAgent):
    def __init__(self):
        super().__init__(
            model="openai:gpt-4o-mini",
            tools=[my_custom_tool],  # Use custom tools
            system_prompt="...",
        )
```

## Understanding Observations

Each step, your agent receives an observation with:

```python
{
    "step": 1,
    "task": {"id": "...", "description": "..."},
    "last_action": {...},  # Previous action you took
    "last_action_result": {...},  # Result of that action
    "visible_state": {...},  # Task-specific state
    "budget_remaining": {"steps": 199, "tool_calls": 39}
}
```

The base class formats this into a prompt automatically.

## Testing Your Agent

### Unit Tests
Test schemas and tools without LLM calls:

```python
from agent_bench.integrations.pydantic_ai import ListDirAction

def test_my_tool():
    action = list_dir("/app")
    assert action.type == "list_dir"
    assert action.args["path"] == "/app"
```

### Mock Tests
Use pydantic-ai's TestModel for fast CI tests:

```python
from pydantic_ai.models.test import TestModel

agent = PydanticAIAgent(model="test", tools=filesystem_tools, system_prompt="...")
TestModel.set_result(ListDirAction.create("/app"))
action = agent.act()
```

### Live Tests
Run against real tasks (requires API key):

```bash
agent-bench run --agent agents/my_agent.py --task filesystem_hidden_config@1 --seed 42
```

## Interactive Wizard

Use the wizard to select your agent interactively:

```bash
agent-bench interactive
# Select: agents/pydantic_ai_agent.py
# Task: filesystem_hidden_config@1
# Seed: 42
```

## Troubleshooting

**"pydantic-ai not installed"**
```bash
pip install -e ".[pydantic]"
```

**"API key not set"**
```bash
export OPENAI_API_KEY=your-key
# or use a different provider
```

**"Action validation failed"**
- Check that your tools return valid ActionModel types
- Verify args match the expected schema

**"Budget exceeded"**
- Optimize your system prompt to reduce unnecessary tool calls
- Use more efficient exploration strategies

## Next Steps

- Explore other tasks: `rate_limited_api@1`, `log_alert_triage@1`
- Build custom tool registries for your domain
- Experiment with different LLM providers and prompts
- Check out the full integration code in `agent_bench/integrations/pydantic_ai/`
