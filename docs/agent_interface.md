# Agent Interface Contract (v0)

This document defines what an agent is, how it interacts with tasks, and what the harness expects.

## 1. Core definition
An agent is a stateful control loop that:
- Receives observations
- Decides on a single action
- Updates internal state
- Repeats until termination

## 2. Required agent API
Every agent must expose:
```
class Agent:
    def reset(self, task_spec: dict) -> None:
        ...

    def observe(self, observation: dict) -> None:
        ...

    def act(self) -> dict:
        ...
```
No async. No callbacks. No streaming.

## 3. Lifecycle
- Initialization: instantiate once per run
- Reset: `agent.reset(task_spec)`
- Observe → Act loop per step

## 4. Observation contract
Observations are fully structured. No free-form text.
Fields are stable and always present.

## 5. Action contract
Agents return a single JSON-serializable action:
```
{
  "type": "read_file",
  "args": {
    "path": "/app/config.yaml"
  }
}
```
Invalid action causes immediate failure.

## 6. State & memory
Agents may keep internal state. The harness does not inspect internals.

## 7. Error handling expectations
Agents should notice failures, retry conservatively, and replan when necessary.

## 8. Budget awareness
Agents receive remaining budgets and must not exceed them.

## 9. Termination semantics
Agents cannot terminate themselves explicitly.

## 10. Determinism expectations
Given identical inputs, agent behavior should be reproducible.

## 11. Reference agent compliance
The reference agent implements this exact interface and gets no special privileges.

## 12. Common failure modes (intentional)
This contract exposes hidden coupling, brittle assumptions, and poor recovery.
