---
description: Bring an OpenAI Agents Python app into the TraceCore workflow
---

# OpenAI Agents Python guide

This guide shows how to take a Python app built with the OpenAI Agents SDK and add the TraceCore evaluation loop without rebuilding the app from scratch.

## Who this is for

Use this guide if you already have:

- a Python codebase using `openai-agents`
- an app surface you can run locally
- a desire to validate agent behavior with repeatable scenarios instead of relying only on demos

If you want a complete example first, start with [`tracecore-openai`](https://github.com/justindobbs/tracecore-openai). It is the reference implementation for the workflow described here.

## The mental model

TraceCore does not replace your OpenAI Agents application.

Instead, it adds a deterministic evaluation layer around it:

- **Live mode** lets you run the app normally with the OpenAI Agents SDK.
- **Deterministic mode** gives you a stable local verification path for known scenarios.
- **TraceCore tasks and adapters** turn those scenarios into repeatable evidence.

That means your development loop becomes:

```bash
tracecore run --agent <adapter> --task <task@version> --seed 0
tracecore verify --latest
tracecore inspect --run <run_id>
tracecore bundle seal --latest
```

## Install the right dependencies

If you are adding TraceCore to an existing project, install the main package plus the OpenAI Agents extra:

```bash
pip install tracecore[openai_agents]
```

For local repo work, keep `tracecore` and your app dependencies in the same virtual environment so the CLI and your project import the same packages.

## Recommended architecture

The easiest integration shape has four layers:

### 1. App/runtime layer

This is your normal OpenAI Agents application code.

Examples:

- FastAPI routes
- background workers
- service functions that call `Runner.run(...)`
- tool definitions and handoff logic

Keep this layer focused on product behavior.

### 2. Deterministic verification mode

Add a repo-local deterministic mode that can answer the same scenario inputs without requiring live model calls.

Typical approach:

- check an environment variable such as `TRACECORE_OPENAI_FAKE_RUNNER`
- route scenario requests to deterministic fake responses
- keep the outputs stable enough for local regression checks

This is the bridge between a live app and a testable evaluation flow.

### 3. TraceCore adapter agents

Expose small adapter agents that implement the TraceCore loop:

- `reset(task_spec)`
- `observe(observation)`
- `act()`

These agents do not need to contain your whole product. Their job is to drive one deterministic evaluation scenario against your app surface and commit the relevant output.

In `tracecore-openai`, the adapter agents:

- submit a known prompt or issue
- inspect the last action result
- write the final output into the task state with `set_output`

### 4. Repo-local TraceCore tasks

Register evaluation tasks that describe the scenarios you care about.

A minimal task package includes:

- `task.toml`
- `setup.py`
- `actions.py`
- `validate.py`

For an adjacent repo, publish or expose them through the `agent_bench.tasks` entry-point group so `tracecore` can discover them naturally.

## Minimal file layout

A practical layout looks like this:

```text
your_repo/
  agent-bench.toml
  agents/
    chat_assistant_agent.py
    support_triage_agent.py
  your_app/
    apps/
    shared/
    tasks/
    tracecore_tasks.py
```

The important pieces are:

- `agent-bench.toml` for defaults
- `agents/` for the TraceCore adapter agents
- repo-local task directories with manifests and validators
- one registration module that exposes `agent_bench.tasks`

## Configure `agent-bench.toml`

Use `agent-bench.toml` to make the native loop less repetitive:

```toml
[defaults]
agent = "agents/chat_assistant_agent.py"
task = "chat_assistant_example@1"
seed = 0

[agent."agents/chat_assistant_agent.py"]
task = "chat_assistant_example@1"
seed = 0
```

This lets `tracecore run` and follow-up commands stay close to the current repo context.

## Register tasks through entry points

In your package metadata, expose the task registration function:

```toml
[project.entry-points."agent_bench.tasks"]
your_repo_tasks = "your_app.tracecore_tasks:register"
```

Your `register()` function should return task descriptors pointing at the repo-local task directories.

## Recommended onboarding flow

For a first-run experience, teach developers this sequence:

### 1. Run the app normally

Start the app in live mode and make sure the user-facing workflow makes sense.

### 2. Switch to deterministic mode

Enable the fake deterministic path with an environment variable.

### 3. Run the native TraceCore loop

```bash
tracecore run --agent agents/chat_assistant_agent.py --task chat_assistant_example@1 --seed 0
tracecore verify --latest
tracecore bundle seal --latest
```

### 4. Inspect and compare as needed

```bash
tracecore inspect --run <run_id>
tracecore diff <run_a> <run_b>
tracecore runs summary --limit 5
```

This gives the team one simple habit: run, verify, inspect, bundle.

## What should stay repo-local

Keep these concerns in your own repo:

- app routes and product UX
- OpenAI Agents instructions, handoffs, and tools
- deterministic fake-runner logic
- scenario-specific task definitions
- adapter agents tied to your app surface

## What TraceCore provides

TraceCore should provide:

- the canonical CLI workflow
- artifact persistence and verification
- bundle operations
- dashboard and inspection surfaces
- the adapter contract and task/plugin discovery model

## Common mistakes to avoid

- treating live hosted runs as if they were deterministic evidence
- skipping a dedicated deterministic mode for local verification
- hiding task registration in undocumented packaging behavior
- forcing new users to memorize run IDs instead of using `--latest`
- documenting `agent-bench` as the default command instead of `tracecore`

## Prompt for your coding agent

Most teams will use an AI coding assistant to wire this up. Use the dedicated scaffold prompt here:

- [`OpenAI Agents scaffold prompt`](openai_agents_scaffold_prompt.md)

## Reference implementation

Use `tracecore-openai` as the concrete model for:

- deterministic fake-runner mode
- OpenAI Agents runtime wrapper
- TraceCore adapter agents
- repo-local task registration
- a small but complete run -> verify -> bundle loop

Once that workflow feels natural in one repo, you can reuse the same pattern in other OpenAI Agents Python projects.
