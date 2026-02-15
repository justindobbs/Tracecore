# OpenClaw Quickstart (TraceCore)

This guide shows how to run an OpenClaw-style agent on TraceCore and how to adapt
existing agent loops to the `reset/observe/act` contract.

## 1. What TraceCore expects
Your module must expose a class named `Agent` (or any class that implements
`reset`, `observe`, and `act`). The harness instantiates the class once per run.

See `docs/agent_interface.md` for the full contract.

## 2. Minimal adapter pattern
If your OpenClaw agent already has a stateful loop, wrap it so the harness can call
`reset`, `observe`, and `act` directly.

```python
from __future__ import annotations


class Agent:
    def __init__(self):
        self._agent = None
        self._last_obs = None

    def reset(self, task_spec: dict) -> None:
        # TODO: initialize your OpenClaw agent from task_spec.
        # Example: self._agent = MyOpenClawAgent(task_spec)
        self._agent = None
        self._last_obs = None

    def observe(self, observation: dict) -> None:
        # Store the structured observation so act() can use it.
        self._last_obs = observation

    def act(self) -> dict:
        # TODO: call your OpenClaw planner with self._last_obs and return an action dict.
        # Example: return self._agent.step(self._last_obs)
        return {"type": "noop", "args": {}}
```

Notes:
- Actions must match the task's allowed actions (see the task's `README.md`).
- Observations are structured dicts, not free-form text. Avoid parsing strings.
- Invalid actions fail the run immediately.

## 3. First run
Point the CLI at your adapter and run a deterministic task.

```bash
agent-bench run --agent path/to/your_agent.py --task filesystem_hidden_config@1 --seed 42
```

If you prefer the UI:

```bash
agent-bench dashboard --reload
```

Then set the agent path and task to the same values in the web form.

## 4. Common OpenClaw-to-Bench mapping tips
- Tool calls: map OpenClaw tool identifiers to the task's `action` names.
- State: keep your OpenClaw memory or planner state inside the Agent instance.
- Budgets: use the observation fields that report remaining steps/tool calls.
- Determinism: avoid randomness unless it is seeded from `task_spec` or observation.

## 5. Troubleshooting
- "No compatible agent class found": ensure the module exports `Agent` or a class
  with `reset/observe/act`.
- "Invalid action": compare your action dict to the task docs for required fields.
- "Budget exceeded": reduce exploratory calls or add early termination logic.

Once this works, move on to `rate_limited_api@1` and `rate_limited_chain@1` to
exercise retry logic and long-horizon behavior.
