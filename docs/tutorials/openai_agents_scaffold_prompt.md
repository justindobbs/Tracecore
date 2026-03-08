---
description: Copy-paste prompt for scaffolding TraceCore into an OpenAI Agents Python repo
---

# OpenAI Agents scaffold prompt

Use the prompt below with your coding assistant to scaffold TraceCore integration into an existing Python project that uses the OpenAI Agents SDK.

```text
I have a Python project that uses the OpenAI Agents SDK, and I want you to scaffold TraceCore integration for it using the same pattern as tracecore-openai.

Goals:
- keep my existing app surface intact
- add a deterministic verification mode for fixed scenarios
- add TraceCore-compatible adapter agents with reset/observe/act
- add repo-local TraceCore tasks and register them through the agent_bench.tasks entry-point group
- add agent-bench.toml defaults so I can use the native tracecore CLI naturally
- prefer tracecore as the documented command name, not agent-bench

Please do the following:
1. Inspect my existing project structure and identify the app entry points, OpenAI Agents runtime code, and any routes or functions that should be exercised by verification scenarios.
2. Create a deterministic fake-runner mode that can respond to a small set of fixed evaluation inputs without calling live models.
3. Add one or two TraceCore adapter agents under an agents/ directory. Each adapter should implement reset(task_spec), observe(observation), and act(), and should drive one deterministic evaluation scenario against the app.
4. Add repo-local task directories with task.toml, setup.py, actions.py, and validate.py for those scenarios.
5. Add a registration module that exposes the tasks through project.entry-points."agent_bench.tasks" in pyproject.toml.
6. Add agent-bench.toml defaults for the primary agent/task pair.
7. Update README or onboarding docs so the workflow is:
   - run the app normally
   - switch to deterministic mode
   - run tracecore run
   - run tracecore verify --latest
   - optionally inspect, diff, and bundle
8. Keep changes minimal and additive. Do not redesign the app.

Implementation requirements:
- use my existing Python environment and dependency manager
- do not hardcode secrets or API keys
- keep imports at the top of files
- make the generated code immediately runnable
- follow the tracecore-openai integration shape where possible

Deliverables:
- the new/updated files
- a short explanation of how the deterministic mode works
- exact commands I should run first to verify the integration
```
