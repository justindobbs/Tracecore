---
description: CI baseline compare workflow
---

# CI Baseline Compare Workflow

Use the reusable GitHub Actions workflow in `.github/workflows/baseline-compare.yml` to run a task and compare the resulting run artifact against a baseline run.

## Reusable workflow usage
```yaml
jobs:
  compare:
    uses: ./.github/workflows/baseline-compare.yml
    with:
      agent_path: agents/toy_agent.py
      task_ref: filesystem_hidden_config@1
      seed: "0"
      baseline: .agent_bench/baselines/rate_limited_chain_chain_agent.json
      require_success: "true"
      max_steps: "200"
      max_tool_calls: "50"
      max_step_delta: "15"
      max_tool_call_delta: "10"
```

## Manual trigger
You can also run the workflow from the Actions tab using `workflow_dispatch` inputs.

## Dedicated chain-agent workflow
This repo also ships `.github/workflows/chain-agent-baseline.yml`, which runs the reusable workflow for:
- agent: `agents/chain_agent.py`
- task: `rate_limited_chain@1`
- baseline: `.agent_bench/baselines/rate_limited_chain_chain_agent.json`

Triggers: pull requests to `main`, pushes to `main`, and manual dispatch.

## Notes
- `baseline` accepts either a run ID or a path to a run artifact.
- Policy gates are optional; omit them or pass an empty string to disable a check.
- `max_step_delta`/`max_tool_call_delta` compare the current run to the baseline run metrics.
- The repo includes `.agent_bench/baselines/rate_limited_chain_chain_agent.json` as a checked-in reference baseline.
- Exit codes: `0` (identical), `1` (different), `2` (incompatible task/agent).
- The workflow uploads `.agent_bench/runs` and `run.json` as artifacts for inspection.
