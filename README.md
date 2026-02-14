# Agent Bench
[![Tests](https://github.com/justindobbs/Agent-Bench/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/justindobbs/Agent-Bench/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/badge/coverage-tracking_pending-lightgrey?logo=pytest)](https://github.com/justindobbs/Agent-Bench/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A lightweight benchmark for action-oriented agents inspired by the OpenClaw style—planner loops, tool APIs, partial observability—but open to any implementation that satisfies the harness.

Agent Bench evaluates whether an agent can operate—not just reason.
No LLM judges. No vibes. No giant simulators.

If your agent can survive this benchmark, it can probably survive production.


## Framing the idea
Terminal Bench works because it:

- Evaluates agents via real tasks, not synthetic prompts
- Uses a simple, opinionated interface (a terminal)
- Is cheap to run, easy to extend, and hard to game

An operations-focused benchmark should do the same, but centered on:

- Action-oriented agents with tool APIs
- Environment interaction and partial observability
- Longish horizons with state, retries, and recovery

In practice, this covers:
- OpenClaw-native agents
- Custom planner loops wired into REST or filesystem tools
- Orchestration agents (e.g., TaskWeaver, AutoGPT-style) that can wrap the simple `reset/observe/act` interface

Think of it less as "benchmarking a model" and more as benchmarking an agent loop end-to-end.

## What makes these agents distinct?
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

Agent Bench answers a different question:
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

## Task categories (operations-native)
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
agent-bench run \
  --agent agents/toy_agent.py \
  --task filesystem_hidden_config@1 \
  --budget steps=200,tool_calls=40 \
  --seed 42
```

Each task ships with a harness, fake environment, and validator. Agents only see what they’re allowed to see.

## Why this matters (and what’s missing today)
Most agent benchmarks collapse back into single-prompt exams. They rarely measure recovery, operational competence, or whether the agent can survive unattended. Agent Bench surfaces engineering-quality differences and rewards boring-but-correct behavior.

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
You provide any agent that implements the documented interface.
We provide a task harness.
The agent runs until:
- It succeeds
- It fails
- It runs out of budget

No human in the loop. No retries.

## Example
```sh
agent-bench run \
  --agent agents/toy_agent.py \
  --task filesystem_hidden_config@1 \
  --seed 42

# Replay a prior run_id (defaults to recorded agent/task/seed, but you can override):
agent-bench run --replay <run_id> --seed 42
```

If `agent-bench` isn’t on your PATH yet, call it via Python:

```powershell
python -m agent_bench.cli --agent agents/toy_agent.py --task filesystem_hidden_config@1 --seed 42
```

Every CLI run writes a JSON artifact under `.agent_bench/runs/<run_id>.json`. Inspect them directly, or list them via:

```sh
agent-bench runs list --limit 5
```

Want to zero in on a specific outcome? Use the structured failure taxonomy filter:

```sh
agent-bench runs list --failure-type timeout --limit 5
agent-bench runs list --failure-type success --limit 5  # only successful runs
```

The same buckets surface in the Web UI’s **Recent Runs** list, where each entry is labeled
`Success` or `Failure — <type>` so you can spot budget exhaustion vs. invalid actions at a glance.

Need a quick aggregate of how an agent performs on a task? Use the baseline helper:

```sh
agent-bench baseline --agent agents/toy_agent.py --task filesystem_hidden_config@1
```

It emits success rate, average steps/tool calls, and links back to the latest trace for that agent/task pair. Add `--export` to persist a frozen snapshot for the web UI:

```sh
agent-bench baseline --export        # writes .agent_bench/baselines/baseline-<ts>.json
agent-bench baseline --export latest # custom filename in the baselines folder
```

The Baselines tab in the UI only shows a "Latest published" card after you export at least once.

On Windows, the installer drops `agent-bench.exe` into `%APPDATA%\Python\Python312\Scripts` (or whatever version you’re using). Add that folder to PATH once and the short command will work everywhere:

1. Press **Win + R**, type `rundll32 sysdm.cpl,EditEnvironmentVariables`, and hit Enter.
2. Under *User variables*, select **Path** → **Edit** → **New**.
3. Paste the Scripts path reported by pip (run `python -m site --user-site` and swap `site-packages` for `Scripts`, e.g., `C:\Users\you\AppData\Roaming\Python\Python312\Scripts`).
4. Move it near the top, click **OK** on all dialogs, then open a new terminal.
5. If `agent-bench` is still not found, reinstall the package (`pip install -e .` inside the repo) so the entry point is created in that Scripts folder.

> Prefer a one-step install? `pipx install -e .` drops its own shim into `%USERPROFILE%\.local\bin` and handles PATH automatically.

## Minimal Web UI (Optional)
Prefer sliders and buttons over the CLI? Spin up the lightweight FastAPI form:

```sh
pip install -e .[dev]
agent-bench dashboard --host 127.0.0.1 --port 8000 --reload
```

> Tip: create a virtual environment first (e.g., `python -m venv .venv && .venv\Scripts\activate` on Windows) so the FastAPI deps stay isolated. See the official FastAPI installation guide for more platform-specific options: <https://fastapi.tiangolo.com/#installation>

Then visit [http://localhost:8000](http://localhost:8000) to:
- Pick any agent module under `agents/`
- Choose a task (`filesystem_hidden_config@1`, `rate_limited_api@1`, etc.) and seed
- Launch runs, inspect structured JSON results (seed included), and drill into traces
- Replay a prior run by pasting its `run_id` and optionally overriding the seed/agent/task

The UI intentionally ships with **no** Node/Vite stack—just FastAPI + Jinja—so you can layer more elaborate frontends later without losing the minimal flow.

Output:
```json
{
  "task_id": "filesystem_hidden_config",
  "version": 1,
  "seed": 42,
  "success": true,
  "failure_reason": null,
  "failure_type": null,
  "steps_used": 37,
  "tool_calls_used": 12
}
```

### Diagnostics workflow

1. **Run & persist** — both the CLI and the web UI call the same harness and automatically persist artifacts under `.agent_bench/runs/` with metadata (`run_id`, `trace_id`, timestamps, harness version, trace entries).
2. **Inspect traces** — load [http://localhost:8000/?trace_id=<run_id>](http://localhost:8000/?trace_id=%3Crun_id%3E) to jump straight to the trace viewer, or fetch raw JSON via `/api/traces/<run_id>`.
3. **Compare outcomes** — use `agent-bench baseline ...` or the UI baseline table to spot regressions (success rate, average steps/tool calls) before publishing results.
4. **Freeze specs** — once a run set looks good, tag the task versions + harness revision so those run IDs remain reproducible proof of behavior.
5. **Manual verification** — before freezing or sharing results, run through `docs/manual_verification.md` to replay the CLI + UI flows end-to-end.

## What we measure
Per task:
- Success / failure
- Steps taken
- Tool calls
- Error count

Across a suite:
- Success rate
- Aggregate efficiency metrics

See [SPEC_FREEZE.md](SPEC_FREEZE.md) for the frozen v0.1.0 task list (including the new `rate_limited_chain@1` pain task) and the rules for bumping versions.

We deliberately avoid:
- LLM-based judges
- Natural language grading
- Weighted composite scores

## Reference agent
Agent Bench ships with a minimal reference agent.
It is:
- Conservative
- State-driven
- Explicit about errors
- Boring on purpose

If your agent can’t outperform the reference agent, that’s a signal.

Reference implementations:
- `agents/toy_agent.py` — solves filesystem discovery tasks.
- `agents/rate_limit_agent.py` — handles classic rate-limit retry flows (`rate_limited_api@1`).
- `agents/chain_agent.py` — completes the chained handshake + rate-limit pain task (`rate_limited_chain@1`).
- `agents/cheater_agent.py` — intentionally malicious “cheater sim” that tries to read hidden state; the sandbox should block it with a `sandbox_violation` so you can prove the harness defenses work.

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
Agent Bench does not aim to:
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
