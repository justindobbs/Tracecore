# Contributing to TraceCore

Thanks for your interest in contributing. TraceCore is opinionated by design — contributions that preserve determinism, mechanical validation, and sandboxed execution are most welcome.

## Quick start

> **Just want to use TraceCore?** Install from PyPI: `pip install tracecore`

Contributors need an editable install to keep tasks and CLI entries in sync with the working tree:

```bash
git clone https://github.com/justindobbs/Tracecore.git
cd Tracecore
python -m venv .venv && .venv\Scripts\activate   # Windows
# source .venv/bin/activate                       # macOS/Linux
pip install -e .[dev]
python -m pytest
```

All tests must pass before opening a pull request.

## What to contribute

### New tasks
Tasks are the highest-value contribution. A good task:
- Is deterministic given a fixed seed
- Runs in seconds on a laptop
- Has exactly one success condition checked by a mechanical validator
- Requires no internet access, GPU, or external services

See [`docs/task_harness.md`](docs/task_harness.md) for the full task contract and [`docs/task_plugin_template.md`](docs/task_plugin_template.md) for a ready-to-copy layout.

Validate your task before submitting:
```bash
agent-bench tasks validate --path tasks/your_task_name
```

### New agents

The fastest way to start a new agent is the scaffold command:

```bash
agent-bench new-agent my_agent
# creates agents/my_agent_agent.py with the correct reset/observe/act interface
```

The generated stub includes inline docstrings explaining the action schema, a budget-guard check (`remaining_steps` / `remaining_tool_calls`), and a `# TODO` marker for your decision logic. Kebab-case names are accepted (`my-agent` → `MyAgentAgent`).

Verify the interface is correct before submitting:
```bash
agent-bench tasks validate --registry   # confirms the task side
agent-bench run --agent agents/my_agent_agent.py --task filesystem_hidden_config@1 --seed 0
```

See [`docs/agents.md`](docs/agents.md) for the full interface contract.

### Bug fixes
- Open an issue first for non-trivial changes so we can align on approach.
- Include a failing test that reproduces the bug.
- Keep fixes minimal — prefer single-line changes over refactors.

### Documentation
- Fix inaccuracies, broken examples, or missing steps.
- Keep the tone spec-like and direct (see [`docs/core.md`](docs/core.md) as a style reference).

## What not to contribute (for now)

- LLM-based judges or scoring
- Tasks that require network access or external APIs
- Multi-agent or concurrent execution models
- Breaking changes to the artifact schema or CLI surface without prior discussion

## Pull request checklist

- [ ] `python -m pytest` passes locally
- [ ] `agent-bench tasks validate --registry` passes (if you touched tasks or registry)
- [ ] New behavior is covered by a test
- [ ] CHANGELOG.md `[Unreleased]` section updated
- [ ] If adding a task: `tasks/registry.json` and `SPEC_FREEZE.md` updated

## Code style

- Python 3.10+, no external dependencies beyond what's in `pyproject.toml`
- `from __future__ import annotations` at the top of every module
- No comments added or removed unless the PR is specifically about documentation
- Run `python -m pytest` — there is no separate linter step required

## Reporting issues

Open a GitHub issue with:
- `python --version` and `pip show agent-bench`
- OS and shell
- The exact command and output (or the `.agent_bench/runs/<run_id>.json` artifact if available)

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for common issues before filing.
