# TraceCore Minimal Start Example

The fastest path from zero to a passing CI-gated agent evaluation with TraceCore.

## What you get

- A minimal agent stub (`my_agent.py`) that runs against a frozen task
- A working `agent-bench.toml` config
- A GitHub Actions workflow that gates on spec compliance and artifact diff

## Prerequisites

```bash
pip install tracecore
tracecore version   # should print: runtime: 1.0.0  spec: tracecore-spec-v1.0
```

## Run the example

```bash
# Run the minimal agent against the filesystem task
tracecore run --agent agents/my_agent.py --task filesystem_hidden_config@1 --seed 0

# Run with strict spec compliance check
tracecore run --agent agents/my_agent.py --task filesystem_hidden_config@1 --seed 0 --strict-spec

# Run all pairings in one command
tracecore run pairing --all
```

## Use the episode config

```bash
# Swap model/budgets without editing the task manifest
tracecore run --from-config episode.json
```

## Diff two runs

```bash
# Compare two run artifacts (use run IDs from .agent_bench/runs/)
tracecore diff <run_id_a> <run_id_b>
tracecore diff <run_id_a> <run_id_b> --format json
```

## Check metrics

```bash
tracecore runs metrics --format table
tracecore runs mttr
```

## CI integration

Copy `.github/workflows/tracecore-ci.yml` to your repository and it will:
1. Lint with Ruff and run all tests on every push/PR
2. Run all pairings under `--strict-spec` to gate on spec compliance
3. Export baseline artifacts on PRs for artifact diff comparison

## Next steps

- Add your own task: see [docs/plugin_contribution_guide.md](../../docs/plugin_contribution_guide.md)
- Customise budgets and model in `episode.json`
- Review the [full spec](../../spec/tracecore-spec-v1.0.md)
