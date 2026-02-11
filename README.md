# Agent Bench
A lightweight benchmark for action-oriented agents.

Agent Bench evaluates whether an agent can operate—not just reason.
No LLM judges. No vibes. No giant simulators.

If your agent can survive this benchmark, it can probably survive production.

## Framing the idea
Terminal Bench works because it:

- Evaluates agents via real tasks, not synthetic prompts
- Uses a simple, opinionated interface (a terminal)
- Is cheap to run, easy to extend, and hard to game

An OpenClaw-flavored benchmark should do the same, but centered on:

- Action-oriented agents with tool APIs
- Environment interaction and partial observability
- Longish horizons with state, retries, and recovery

Think of it less as "benchmarking a model" and more as benchmarking an agent loop end-to-end.

## What makes OpenClaw agents distinct?
(Adjust these if your mental model differs.)

- Planner / policy loop instead of single-shot prompting
- Tool or action interfaces instead of raw chat completions
- Optional memory, world models, or reusable skills
- Strong emphasis on doing, not just responding

So the benchmark should **not** test raw language quality or one-shot reasoning. It should test:

- Decision-making under constraints
- Tool sequencing and dependency management
- Recovery from errors and partial failures
- State tracking over time and across steps

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
1. **Minimal environment, maximal signal**
   - Keep worlds tiny, deterministic, and inspectable: toy filesystems, fake APIs, log streams, local services.
   - No giant simulators or cloud dependencies—everything should run in seconds on a laptop.
2. **Agent-in-the-loop evaluation**
   - Benchmark the entire perception → reasoning → action loop, not a single prompt.
   - Each task specifies initial state, tool interface, validator, and explicit budgets (steps + tool calls).
3. **Binary outcomes first**
   - Success or failure is the headline metric; secondary stats (steps, tool calls, errors) give color.
   - Deterministic tasks + frozen versions make regressions obvious and stop overfitting.
4. **Hard to game, easy to extend**
   - Sandboxed execution, limited affordances, and published hashes keep agents honest.
   - Tasks are small Python packages so contributors can add new scenarios without ceremony.

## Task categories (OpenClaw-native)
### 1. Tool choreography tasks
Goal: stress sequencing, dependency management, and retries.

- *Example:* `rate_limited_api@1` — retrieve an `ACCESS_TOKEN` from a mock API that enforces a deterministic rate limit and transient failures.
- *Signals:* correct tool ordering, retry logic, state retention, graceful degradation.

### 2. Partial observability & discovery
Goal: reward cautious exploration instead of brute force.

- *Example:* “Traverse a directory tree with undocumented schema. Find the real config key without trashing the filesystem.”
- *Signals:* hypothesis updates, selective reads, remembering seen paths, avoiding repeated mistakes.

### 3. Long-horizon maintenance
Goal: ensure persistence, monitoring, and acting at the right moment.

- *Example:* “A service degrades over time. Watch logs, detect the symptom, and apply the correct fix only when needed.”
- *Signals:* patience, trigger detection, not overreacting, applying steady-state playbooks.

### 4. Adversarial-but-fair environments
Goal: test robustness when the world is a little hostile.

- *Example:* flaky tools, malformed API responses, conflicting telemetry that needs disambiguation.
- *Signals:* error recovery, fallback strategies, keeping track of provenance before acting.

## Scoring without overengineering
- Binary success/failure is the scoreboard.
- Secondary metrics: steps taken, tool calls, wall-clock time, error count.
- No LLM judges, no vibes, no composite scores you can’t reason about.

## Interface sketch
Agents run exactly like they would in production: provide an agent, pick a task, respect the budget.

```sh
openclaw-bench run \
  --agent agents/toy_agent.py \
  --task filesystem_hidden_config@1 \
  --budget steps=200,tool_calls=40 \
  --seed 42
```

Each task ships with a harness, fake environment, and validator. Agents only see what they’re allowed to see.

## Why this matters (and what’s missing today)
Most agent benchmarks collapse back into single-prompt exams. They rarely measure recovery, operational competence, or whether the agent can survive unattended. OpenClaw Bench surfaces engineering-quality differences and rewards boring-but-correct behavior.

## Potential pitfalls & guardrails
- **Overfitting to the harness** → Keep suites varied, publish fixtures, encourage new contributions.
- **Agents cheating via inspection** → Sandbox aggressively, freeze binaries, limit visibility.
- **Benchmark drift** → Freeze task versions, publish hashes/seeded assets, require changelog entries.

## What’s in v0
Task suites:
- Filesystem & State
- Tool Choreography
- Long-Horizon & Monitoring
- Adversarial-but-Fair

Shipping tasks:
- `filesystem_hidden_config@1` (filesystem suite): explore a hidden directory tree to find the one true `API_KEY`.
- `rate_limited_api@1` (api suite): classify API errors, respect `retry_after`, and persist the returned `ACCESS_TOKEN`.

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

## Minimal Web UI (Optional)
Prefer sliders and buttons over the CLI? Spin up the lightweight FastAPI form:

```sh
pip install -e .[dev]
uvicorn openclaw_bench.webui.app:app --reload
```

> Tip: create a virtual environment first (e.g., `python -m venv .venv && .venv\Scripts\activate` on Windows) so the FastAPI deps stay isolated. See the official FastAPI installation guide for more platform-specific options: <https://fastapi.tiangolo.com/#installation>

Then visit [http://localhost:8000](http://localhost:8000) to:
- Pick any agent module under `agents/`
- Choose a task (`filesystem_hidden_config@1`, `rate_limited_api@1`, etc.) and seed
- Launch runs and view structured JSON results in the browser

The UI intentionally ships with **no** Node/Vite stack—just FastAPI + Jinja—so you can layer more elaborate frontends later without losing the minimal flow.

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
