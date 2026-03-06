# OpenClaw Quickstart (TraceCore)

This guide shows how to wrap an OpenClaw agent so it runs inside TraceCore's
deterministic episode harness, and how to map OpenClaw concepts to the
`reset/observe/act` contract.

## 1. What TraceCore expects

TraceCore instantiates your agent class once per episode and calls three methods:

| Method | When called | Purpose |
|---|---|---|
| `reset(task_spec)` | Once, before the episode starts | Initialise state from the task definition |
| `observe(observation)` | Before every step | Receive the latest environment state |
| `act() → dict` | After every `observe` | Return the next action |

The class can be named anything; the harness discovers it by scanning the module
for a class that implements all three methods. See `docs/agent_interface.md` for
the full contract and action schema.

## 2. How OpenClaw's agent loop maps to TraceCore

OpenClaw runs an LLM-driven loop internally (`agentCommand` →
`runEmbeddedPiAgent` → `pi-agent-core`). Full details: [Agent Loop](https://docs.openclaw.ai/concepts/agent-loop) · [Agent Runtime](https://docs.openclaw.ai/concepts/agent) · [Configuration Reference](https://docs.openclaw.ai/gateway/configuration-reference).

It streams three event types:

- `lifecycle` — start / end / error signals
- `assistant` — streamed LLM deltas
- `tool` — tool start / update / end events

TraceCore's harness is synchronous and step-based, so the adapter must translate
between the two models. The key insight: **one `act()` call = one tool call
decision**. Your adapter drives OpenClaw's tool selection logic and returns a
single action dict per step.

## 3. Adapter pattern

### 3a. Stateless rule-based adapter (simplest)

If you have a policy function that maps observations to tool calls, wrap it
directly — no OpenClaw runtime needed:

```python
from __future__ import annotations


class OpenClawAdapter:
    """Wraps a rule-based OpenClaw-style policy as a TraceCore agent."""

    def reset(self, task_spec: dict) -> None:
        self.task_spec = task_spec
        self.obs = None
        self.step = 0

    def observe(self, observation: dict) -> None:
        self.obs = observation

    def act(self) -> dict:
        self.step += 1
        remaining_steps = self.obs.get("remaining_steps", 0)
        remaining_tool_calls = self.obs.get("remaining_tool_calls", 0)

        if remaining_steps <= 1 or remaining_tool_calls <= 1:
            return {"type": "wait", "args": {}}

        # Map your OpenClaw tool selection logic here.
        # Return a TraceCore action dict — see the task's README for allowed types.
        # Example for filesystem tasks:
        #   return {"type": "read_file", "args": {"path": "/etc/config"}}
        # Example to submit a final answer:
        #   return {"type": "set_output", "args": {"key": "answer", "value": "..."}}
        return {"type": "wait", "args": {}}
```

### 3b. Plugin hook adapter (intercept OpenClaw's tool decisions)

OpenClaw exposes `before_tool_call` and `after_tool_call` plugin hooks. Use
these to intercept tool decisions and translate them into TraceCore actions
without rewriting your planner:

```python
from __future__ import annotations
from typing import Any


class OpenClawPluginAdapter:
    """Drives an OpenClaw plugin hook pipeline as a TraceCore agent.

    Assumes your OpenClaw plugin populates self._pending_action via
    before_tool_call when given the current observation.
    """

    def __init__(self, plugin) -> None:
        # plugin: an object with before_tool_call(obs) -> action_dict
        self._plugin = plugin
        self._pending_action: dict | None = None
        self.obs: dict | None = None

    def reset(self, task_spec: dict) -> None:
        self.task_spec = task_spec
        self.obs = None
        self._pending_action = None

    def observe(self, observation: dict) -> None:
        self.obs = observation
        # Let the plugin decide the next tool call given the current observation.
        self._pending_action = self._plugin.before_tool_call(observation)

    def act(self) -> dict:
        if self._pending_action is not None:
            action = self._pending_action
            self._pending_action = None
            return action
        return {"type": "wait", "args": {}}
```

### 3c. Session-based adapter (full OpenClaw runtime)

If you want to drive a live OpenClaw agent via its Gateway RPC, call
`agent` / `agent.wait` and translate the `agent_end` payload into a TraceCore
action. This is the most faithful integration but requires a running OpenClaw
gateway (`openclaw agents add <name> --workspace <path>`).

```python
from __future__ import annotations


class OpenClawGatewayAdapter:
    """Drives a live OpenClaw agent via Gateway RPC.

    Requires: openclaw gateway running, openclaw Python SDK installed.
    """

    def __init__(self, agent_id: str, client) -> None:
        self._agent_id = agent_id
        self._client = client  # OpenClaw gateway client
        self.obs: dict | None = None

    def reset(self, task_spec: dict) -> None:
        self.task_spec = task_spec
        self.obs = None

    def observe(self, observation: dict) -> None:
        self.obs = observation

    def act(self) -> dict:
        remaining_steps = (self.obs or {}).get("remaining_steps", 0)
        remaining_tool_calls = (self.obs or {}).get("remaining_tool_calls", 0)
        if remaining_steps <= 1 or remaining_tool_calls <= 1:
            return {"type": "wait", "args": {}}

        # Dispatch to the OpenClaw agent and wait for its tool decision.
        # agent.wait default timeout is 30s; agent runtime default is 600s
        # (agents.defaults.timeoutSeconds in ~/.openclaw/openclaw.json).
        run = self._client.agent(self._agent_id, prompt=str(self.obs))
        result = self._client.agent_wait(run["runId"], timeout_ms=25_000)

        if result.get("status") != "ok":
            return {"type": "wait", "args": {}}

        # Translate the agent_end payload into a TraceCore action dict.
        # Your plugin's agent_end hook should populate result["action"].
        return result.get("action") or {"type": "wait", "args": {}}
```

## 4. OpenClaw → TraceCore concept mapping

| OpenClaw concept | TraceCore equivalent |
|---|---|
| `agentCommand` / `runEmbeddedPiAgent` | `act()` call |
| `before_tool_call` plugin hook | Decision logic inside `act()` |
| `after_tool_call` plugin hook | Read `last_action_result` in next `observe()` |
| `agent_end` hook | Final `set_output` action |
| `agents.defaults.timeoutSeconds` (default 600s) | `tracecore run --timeout <s>` |
| `lifecycle: error` / abort signal | `failure_type: timeout` or `logic_failure` in run artifact |
| Session JSONL (`~/.openclaw/agents/.../sessions/*.jsonl`) | Run artifact (`.agent_bench/runs/<run_id>.json`) |
| Skills snapshot | `task_spec` passed to `reset()` |
| `AGENTS.md` bootstrap context | Task description in `task_spec["description"]` |

## 5. Action schema quick reference

Every `act()` return value must be a dict with at minimum `"type"` and `"args"`.
Common actions across tasks:

```python
# Read a file (filesystem tasks)
{"type": "read_file", "args": {"path": "/path/to/file"}}

# Call an API endpoint (rate-limited API tasks)
{"type": "call_api", "args": {"endpoint": "/status", "method": "GET"}}

# Submit the final answer and end the episode successfully
{"type": "set_output", "args": {"key": "answer", "value": "<your_answer>"}}

# Consume a step without acting (use sparingly — costs a step budget)
{"type": "wait", "args": {}}
```

See the task's `README.md` or `task.toml` for the full allowed-action list.
Invalid action types fail the run immediately with `failure_type: invalid_action`.

## 6. Budget guard

Always check remaining budgets before expensive tool calls. The observation dict
always contains:

```python
obs["remaining_steps"]       # steps left before forced termination
obs["remaining_tool_calls"]  # tool calls left before forced termination
obs["last_action_result"]    # result of the previous action (None on first step)
```

## 7. First run

### Quickest path: `tracecore openclaw`

Navigate to your OpenClaw workspace (where `openclaw.json` lives) and run:

```bash
cd ~/.openclaw/workspace          # or wherever your openclaw.json lives
tracecore openclaw --agent-id <your-agent-id>
```

> **No OpenClaw account yet?** Use the mock workspace in `examples/mock_openclaw_workspace/`
> to try the full workflow offline:
> ```bash
> cd examples/mock_openclaw_workspace
> tracecore openclaw --agent-id log-monitor
> ```

On the first invocation this:
1. Reads `openclaw.json` and locates the `researcher` agent config + prompt file
2. Scaffolds `researcher_adapter_agent.py` in the current directory
3. Prints a hint to fill in `act()` and re-run

> **No OpenClaw install required.** The default adapter is self-contained — `act()` is pure Python and tests run against a deterministic sandboxed environment. Only `--gateway` needs a live OpenClaw gateway.

**If you're in an AI IDE (Windsurf, Cursor, etc.)**, this is the same red-green loop you already use with pytest — except `tracecore` is the test runner (the `agent-bench` alias still works if you have old scripts):

1. Ask your AI agent to pick the right task and run it, e.g.
   > "Read `researcher_adapter_agent.py` and `~/.openclaw/cron/jobs.json`. Pick the most relevant TraceCore task (see §9 table) and run `tracecore openclaw --agent-id researcher --task <task> --seed 0`."
2. The run fails → the AI reads the `failure_type` and trace, rewrites `act()`.
3. Re-run. Repeat until it passes — exactly like fixing a failing pytest test.

If no built-in task matches your agent's purpose, the AI can scaffold a custom one (see §9).

**Manually**, edit the adapter then run against a task you choose:

```bash
# edit researcher_adapter_agent.py — fill in act() logic
tracecore openclaw --agent-id researcher --task filesystem_hidden_config@1 --seed 0
```

See §9 for task suggestions by agent capability.

Once it passes, export a certified bundle:

```bash
tracecore openclaw-export --agent-id researcher
# writes tracecore_export/researcher/ with adapter, prompt, manifest, README
```

To also generate a gateway-wired adapter (requires a running OpenClaw gateway):

```bash
tracecore openclaw --agent-id <your-agent-id> --gateway
```

### Manual path

If you prefer to scaffold manually without an `openclaw.json`:

```bash
tracecore new-agent my_openclaw_adapter
# edit agents/my_openclaw_adapter_agent.py — fill in act() logic
tracecore run --agent agents/my_openclaw_adapter_agent.py \
    --task filesystem_hidden_config@1 --seed 0
```

Or use the Pairings tab in the dashboard for a one-click known-good run:

```bash
tracecore dashboard --reload
# open http://localhost:8000 → Pairings tab → click Launch
```

## 8. Troubleshooting

- **"No compatible agent class found"** — the module must export a class with
  `reset`, `observe`, and `act`. Run `tracecore new-agent` to get a valid stub.
- **`failure_type: invalid_action`** — the action `type` is not in the task's
  allowed list. Check the task's `README.md` for valid types.
- **`failure_type: budget_exceeded`** — add a budget guard (see §6) and reduce
  exploratory calls.
- **`failure_type: timeout`** — the wall-clock limit was hit. Increase with
  `--timeout <seconds>` or reduce per-step latency in your OpenClaw plugin.
- **OpenClaw gateway `agent.wait` returns `status: timeout`** — the default
  wait is 30 s. Pass `timeout_ms` explicitly or increase
  `agents.defaults.timeoutSeconds` in `~/.openclaw/openclaw.json`.
  See [Configuration Reference](https://docs.openclaw.ai/gateway/configuration-reference) for all gateway options.

## 9. Next steps

### Task selection by agent capability

If you're using an AI IDE, ask your agent to match your OpenClaw agent's cron
jobs and skills against this table:

| If your agent does… | Start with this task |
|---|---|
| File search, config lookup, read/write ops | `filesystem_hidden_config@1` |
| API calls with retry / quota awareness | `rate_limited_api@1` |
| Multi-step orchestration across rate-limited services | `rate_limited_chain@1` |
| Log monitoring, alert triage, severity filtering | `log_alert_triage@1` |
| Streaming log analysis, pattern detection | `log_stream_monitor@1` |
| General-purpose / unknown | `filesystem_hidden_config@1` (baseline sanity check) |

If none of the built-in tasks match, ask your AI agent to scaffold a custom
task directory:

> "Create a TraceCore task in `tasks/my_task/` that tests this agent's
> core behaviour. Include `setup/`, `actions/`, `validate/`, and `manifest.json`."

Once `filesystem_hidden_config@1` passes, progress to tasks that exercise
OpenClaw's strengths:

- `rate_limited_api@1` — retry logic and quota management
- `rate_limited_chain@1` — multi-step handshake + rate-limit orchestration
- `log_alert_triage@1` — operations triage with `agents/ops_triage_agent.py`
  as a deterministic baseline before swapping in your OpenClaw agent

Run all known-good pairings as a smoke test after any agent change:

```bash
tracecore run pairing --all
```
