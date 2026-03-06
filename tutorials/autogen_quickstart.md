# AutoGen Quickstart (TraceCore)

This guide shows how to test an AutoGen multi-agent team inside TraceCore's
deterministic benchmark harness, using the automatic adapter generator to
eliminate manual rewrites.

## 1. What TraceCore expects

TraceCore instantiates your agent class once per episode and calls three methods:

| Method | When called | Purpose |
|---|---|---|
| `reset(task_spec)` | Once, before the episode starts | Initialise state from the task definition |
| `observe(observation)` | Before every step | Receive the latest environment state |
| `act() → dict` | After every `observe` | Return the next action |

The class can be named anything; the harness discovers it by scanning the module
for a class that implements all three methods. See `docs/agent_interface.md` for
the full contract.

## 2. How AutoGen's model differs from TraceCore

AutoGen runs **conversational loops** — a team of agents chat back and forth
until a termination condition is met. The entire conversation happens in one
`team.run()` call.

TraceCore runs **step-based episodes** — the harness calls `observe → act` in a
loop, one action per step, with budget enforcement and full observability at
every step.

These are fundamentally different execution models. You can't just wrap
`team.run()` as a black box because:

- TraceCore can't see inside the conversation (no per-step trace)
- TraceCore can't enforce budgets on individual actions
- The conversational output is a final answer, not a sequence of actions

## 3. The three integration approaches

| Approach | How it works | Tradeoff |
|---|---|---|
| **Pure adapter** | Wrap `team.run()` as a black box, return final answer | Simple but loses observability and budget control |
| **Per-step LLM** | Each `act()` = one short AutoGen conversation | True adapter but fragile — LLM must produce valid action JSON every time |
| **Hybrid** (recommended) | Generic state machine handles known patterns; AutoGen team consulted for novel situations | Reliable, fast, fully observable. The state machine is auto-generated. |

The adapter generator (`agent_bench.integrations.autogen_adapter`) implements
the hybrid approach automatically.

## 4. Prerequisites

- Python 3.10+
- An OpenAI API key (set `OPENAI_API_KEY` in your environment)
- Git

## 5. Install

```bash
# Clone TraceCore
git clone https://github.com/justindobbs/Tracecore.git
cd Tracecore

# Install TraceCore in editable mode
pip install -e .

# Install AutoGen dependencies
pip install "autogen-agentchat" "autogen-ext[openai]"
```

Verify both are installed:

```bash
tracecore --help   # legacy `agent-bench` alias still works
python -c "from autogen_agentchat.agents import AssistantAgent; print('AutoGen OK')"
```

## 6. Generate your agent (one command)

```python
from agent_bench.integrations.autogen_adapter import generate_agent

generate_agent(
    task_ref="rate_limited_api@1",
    model="gpt-4o",
    agents=[
        {
            "name": "Worker",
            "system_message": "Execute tools precisely. Report errors to the Supervisor.",
        },
        {
            "name": "Supervisor",
            "system_message": "Review actions. If wrong, correct them. Always output one JSON action.",
        },
    ],
    output_path="agents/my_autogen_agent.py",
)
```

This reads the task's action schema, bakes it into the agent's prompts, and
writes a complete TraceCore-compatible agent file. No manual rewrite needed.

**Default team:** If you omit the `agents` parameter, you get a Worker +
Supervisor pair with sensible defaults.

```python
# Minimal — uses default Worker + Supervisor team
generate_agent("rate_limited_api@1", output_path="agents/my_autogen_agent.py")
```

### All parameters

| Parameter | Default | Description |
|---|---|---|
| `task_ref` | (required) | Task reference like `"rate_limited_api@1"` |
| `model` | `"gpt-4o"` | OpenAI model name |
| `agents` | Worker + Supervisor | List of `{"name", "system_message"}` dicts |
| `class_name` | `"AutoGenTeamAgent"` | Name of the generated Python class |
| `max_turns` | `4` | Max conversation turns per step (when LLM is consulted) |
| `termination_keyword` | `"DONE"` | Keyword that ends the AutoGen conversation |
| `output_path` | `"agents/autogen_agent.py"` | Where to write the file |

## 7. Run the benchmark

```bash
tracecore run --agent agents/my_autogen_agent.py --task rate_limited_api@1 --seed 42
```

Expected output:

```
+-----------------------------------------------------------------------------+
| ✓ SUCCESS  rate_limited_api@1  |  steps: 6  tool_calls: 6                   |
+-----------------------------------------------------------------------------+
```

## 8. View results

### CLI

```bash
# List recent runs
tracecore runs list --limit 5

# Summary table
tracecore runs summary
```

### Dashboard

```bash
tracecore dashboard
# Open http://localhost:8000
```

### Raw JSON

Run artifacts are saved to `.agent_bench/runs/<run_id>.json`.

## 9. What happened — trace walkthrough

The generated agent completed the task in 6 steps with zero LLM calls
(the generic state machine handled everything):

| Step | Action | Result | How the agent decided |
|---|---|---|---|
| 1 | `get_client_config` | Got payload template (client_id + nonce) | First step, no data yet → info-gathering fallback |
| 2 | `call_api /token` | Rate limited (retry_after=2) | Learned data → filled in `call_api` args automatically |
| 3 | `wait(steps=2)` | Advanced virtual time | `rate_limited` error → deterministic wait |
| 4 | `call_api /token` | Temporary failure | After wait → retry previous action |
| 5 | `call_api /token` | **Got token: ACCESS-770487** | `temporary_failure` → retry same action |
| 6 | `set_output` | Stored ACCESS_TOKEN → **SUCCESS** | Found token in result → commit output |

## 10. What the generator produces

The generated agent has three layers:

### Layer 1: Generic reactive state machine (handles ~90% of steps)

These patterns apply to **any** TraceCore task, not just `rate_limited_api`:

- **Learn from responses** — stores data from successful actions (payload
  templates, tokens, configs) in `self.learned_data`
- **Handle errors** — `rate_limited` → wait, `temporary_failure` → retry,
  `bad_request` → re-gather info
- **Extract tokens** — recursively searches results for token/key/secret values
- **Fill args from learned data** — when an action needs `payload`, checks if
  a `payload_template` was learned from a previous response
- **Info-gathering fallback** — on first step or when stuck, picks a no-arg
  action like `get_client_config` or `inspect_status`

### Layer 2: AutoGen team fallback (handles novel situations)

When the state machine doesn't know what to do, it runs a short AutoGen
conversation with your team topology. The prompt includes:

- Task description and current step
- Available actions with required parameters
- Last action and result
- Recent history
- Budget remaining

### Layer 3: Validation guard

If the LLM produces an action with missing required args, the agent falls back
to an info-gathering action instead of failing the run.

## 11. AutoGen ↔ TraceCore concept mapping

| AutoGen concept | TraceCore equivalent |
|---|---|
| `RoundRobinGroupChat` | Step loop (`observe → act`) |
| `AssistantAgent` | Action decision logic inside `act()` |
| `TextMentionTermination` | Task validator (`validate.py`) |
| `tools` parameter | Action surface (`actions.py`) |
| `team.run(task=...)` | `reset(task_spec)` + step loop |
| `model_client` | Used inside `_consult_team()` for LLM fallback |
| `max_turns` | Budget (`steps`, `tool_calls`) |
| Conversation messages | `step_log` + `learned_data` |

## 12. Customizing the generated agent

### Swap team topology

Pass different agents to `generate_agent()`:

```python
generate_agent(
    "rate_limited_api@1",
    agents=[
        {"name": "Analyst", "system_message": "Analyze the task state and propose an action."},
        {"name": "Critic", "system_message": "Challenge the Analyst's proposal. Suggest improvements."},
        {"name": "Executor", "system_message": "Pick the best action. Output one JSON object. Say DONE."},
    ],
    output_path="agents/three_agent_team.py",
)
```

### Add domain-specific system messages

Customize the system messages to match your agent's expertise:

```python
generate_agent(
    "rate_limited_api@1",
    agents=[
        {
            "name": "APIExpert",
            "system_message": (
                "You are an API integration specialist. "
                "Always check rate limit headers. "
                "Use exponential backoff for retries."
            ),
        },
    ],
    max_turns=2,  # Single agent, fewer turns needed
    output_path="agents/api_expert.py",
)
```

### Add deterministic rules to the generated code

The generated `act()` method has a clear comment showing where to insert
custom state-machine rules. Edit the generated file directly:

```python
# In the generated act() method, before the AutoGen team fallback:

# Custom rule: if we see a specific error, handle it deterministically
if action_type == "call_api" and last_result:
    if last_result.get("error") == "auth_required":
        return {"type": "authenticate", "args": {"method": "oauth2"}}
```

## 13. When you need more than the generator

The auto-generated agent works well for tasks that follow common patterns
(info-gathering → API calls → error handling → output). For tasks that require
complex multi-step reasoning or domain-specific logic, you may want to:

1. **Start with the generator** — get a working baseline
2. **Run the benchmark** — see where it fails
3. **Add deterministic rules** — handle the failure patterns
4. **Iterate** — the red-green loop, just like fixing a failing test

This is the same workflow you'd use with pytest — except `tracecore` is the
test runner (with `agent-bench` still available as a compatibility alias) and the "test" is a full task episode.

## 14. Try other tasks

```bash
# List available tasks
tracecore tasks

# Generate an agent for a different task
python -c "
from agent_bench.integrations.autogen_adapter import generate_agent
generate_agent('filesystem_hidden_config@1', output_path='agents/fs_agent.py')
"

# Run it
tracecore run --agent agents/fs_agent.py --task filesystem_hidden_config@1 --seed 0
```

### Task suggestions by agent capability

| If your agent does… | Start with this task |
|---|---|
| File search, config lookup, read/write ops | `filesystem_hidden_config@1` |
| API calls with retry / quota awareness | `rate_limited_api@1` |
| Multi-step orchestration across services | `rate_limited_chain@1` |
| Log monitoring, alert triage | `log_alert_triage@1` |
| General-purpose / unknown | `filesystem_hidden_config@1` (baseline) |

## 15. Troubleshooting

- **`failure_type: invalid_action`** — the action `type` is not in the task's
  allowed list, or required args are missing. The generator's validation guard
  should catch most of these, but check the trace for details.
- **`failure_type: budget_exhausted`** — the agent used too many steps or tool
  calls. Add deterministic rules to avoid unnecessary LLM consultations.
- **`No compatible agent class found`** — the module must export a class with
  `reset`, `observe`, and `act`.
- **`ModuleNotFoundError: autogen_agentchat`** — install AutoGen:
  `pip install "autogen-agentchat" "autogen-ext[openai]"`
- **`OPENAI_API_KEY` not set** — the AutoGen team fallback needs an API key.
  The generic state machine doesn't, so if the state machine handles everything,
  no API key is needed.

## 16. Summary

| What | Where |
|---|---|
| Adapter generator | `agent_bench/integrations/autogen_adapter.py` |
| Generated agent | `agents/<your_agent>.py` |
| Run artifacts | `.agent_bench/runs/<run_id>.json` |
| Dashboard | `tracecore dashboard` → `http://localhost:8000` |
| Agent interface spec | `docs/agent_interface.md` |
| Task harness spec | `docs/task_harness.md` |
