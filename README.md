# OpenClaw Bench
A lightweight benchmark for action-oriented agents.

OpenClaw Bench evaluates whether an agent can operate—not just reason.
No LLM judges. No vibes. No giant simulators.

If your agent can survive this benchmark, it can probably survive production.

## Why this exists
Most benchmarks answer questions like:
- Can the model reason?
- Can it write the right patch?
- Can it roleplay an agent?

OpenClaw Bench answers a different question:
Can this agent run unattended and get the job done without breaking things?

We test:
- Tool sequencing
- Error recovery
- State tracking
- Long-horizon behavior
- Boring, reliable decision-making

## Design principles
- Agent-in-the-loop: we benchmark full control loops, not single responses.
- Realistic but minimal environments: local, deterministic, fast.
- Binary outcomes: tasks either succeed or fail.
- Hard to game: sandboxed environments, frozen task versions, explicit budgets.
- Cheap and hackable: easy to add tasks, easy to run in CI.

## What’s in v0
Task suites:
- Filesystem & State
- Tool Choreography
- Long-Horizon & Monitoring
- Adversarial-but-Fair

Each task:
- Defines an initial environment
- Exposes a constrained action interface
- Has a single, deterministic success condition

## How it works
You provide an agent (your OpenClaw implementation).
We provide a task harness.
The agent runs until:
- It succeeds
- It fails
- It runs out of budget

No human in the loop. No retries.

## Example
```sh
openclaw-bench run \
  --agent agents/toy_agent.py \
  --task filesystem_hidden_config@1 \
  --seed 42
```

Output:
```json
{
  "task_id": "filesystem_hidden_config",
  "version": 1,
  "seed": 42,
  "success": true,
  "failure_reason": null,
  "steps_used": 37,
  "tool_calls_used": 12
}
```

## What we measure
Per task:
- Success / failure
- Steps taken
- Tool calls
- Error count

Across a suite:
- Success rate
- Aggregate efficiency metrics

We deliberately avoid:
- LLM-based judges
- Natural language grading
- Weighted composite scores

## Reference agent
OpenClaw Bench ships with a minimal reference agent.
It is:
- Conservative
- State-driven
- Explicit about errors
- Boring on purpose

If your agent can’t outperform the reference agent, that’s a signal.

## Adding a task
Tasks are small and self-contained.
A task defines:
- Environment setup
- Available actions/tools
- Success validator
- Budget defaults

If your task:
- Requires internet access
- Needs a GPU
- Takes minutes to run

It probably doesn’t belong here.

## Non-goals
OpenClaw Bench does not aim to:
- Benchmark raw language quality
- Measure creativity
- Replace SWE-bench or Terminal Bench
- Simulate the real world

It tests operational competence, nothing more.

## Status
This project is early and opinionated.
Expect:
- Breaking changes
- Small task suites
- Strong opinions

If you disagree, open an issue—or better, a PR.

One-line summary:
Terminal Bench, but for agents that actually have to do things.
