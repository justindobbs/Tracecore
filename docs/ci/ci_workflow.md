---
description: CI baseline compare workflow
---

# CI Baseline Compare Workflow

TraceCore CI integrates in two complementary patterns. Choose based on your workflow:

## Which pattern to use

| Pattern | When to use | Gate command |
| --- | --- | --- |
| **Record/Replay (bundle-based)** | New workflow. Record once locally or via manual dispatch; replay/strict enforces the sealed bundle on every PR. | `--replay-bundle <path> --strict` |
| **Baseline compare (artifact-based)** | Existing workflow. Compare a fresh run artifact against a checked-in JSON baseline using policy gates (step/tool-call delta thresholds). | `tracecore baseline --compare` |

The record/replay pattern is the recommended approach for new projects. The baseline-compare pattern is preserved for backwards compatibility.

If you want a maintained GitHub-native wrapper around `tracecore run` and `tracecore verify`, see [`tracecore-action`](https://github.com/justindobbs/tracecore-action). Public external consumer-validation examples for that wrapper live in [`tracecore-test`](https://github.com/justindobbs/tracecore-action-test).

## Mental model: record locally, enforce in CI

```
[Developer, once]
tracecore run --agent ... --task ... --seed 0 --record
git add .agent_bench/baselines/<run_id>
git commit -m "seal: baseline for my_task@1"

[CI, every PR]
tracecore run --agent ... --task ... --seed 0 \
  --replay-bundle .agent_bench/baselines/<run_id> --strict
```

If the trace diverges from the sealed bundle, CI exits 1 and uploads the run log for triage.

## Repo-provided workflow patterns
- **`ci/templates/github-record-replay.yml`**: copy-ready GitHub Actions workflow — records via `workflow_dispatch`, enforces replay/strict on pull requests, uploads artifacts on success and failure.
- **`ci/templates/gitlab-record-replay.yml`**: copy-ready GitLab pipeline — manual record stage, merge-request strict gate, artifact upload.
- Both templates now emit `verify.json` from `tracecore baseline --verify <bundle>` during the record job so the sealed bundle has a deterministic integrity report committed alongside the artifacts.
- **`scripts/policy_gate.py`** and the reusable GitHub workflow also accept `verify.json` so CI can fail immediately if bundle integrity drifts; pass `--bundle-verify-json` to `policy_gate.py` or rely on the `Enforce bundle verify report` step in `.github/workflows/baseline-compare.yml`.
- **`.github/workflows/baseline-compare.yml`** (reusable, legacy): accepts agent, task, seed, baseline, and optional policy gates; emits run artifacts plus `run.json`; fails with exit code `1` for mismatches and `2` for incompatible agent/task pairs.
- **`.github/workflows/chain-agent-baseline.yml`** (caller, legacy): pins the chain agent + `rate_limited_chain@1` baseline.

Treat these as the source of truth for command order, artifact upload, and failure messaging.

For teams that prefer consuming a published GitHub Action instead of copying workflow templates, `tracecore-action` provides a thinner integration surface around these same TraceCore CLI flows.

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

## GitHub Actions example (policy gates + artifacts)
```yaml
name: tracecore-ci

on:
  pull_request:
  workflow_dispatch:

jobs:
  tracecore-compare:
    uses: ./.github/workflows/baseline-compare.yml
    with:
      agent_path: agents/chain_agent.py
      task_ref: rate_limited_chain@1
      seed: "0"
      baseline: .agent_bench/baselines/rate_limited_chain_chain_agent.json
      require_success: "true"
      max_steps: "180"
      max_tool_calls: "60"
      max_step_delta: "10"
      max_tool_call_delta: "5"
```

**Failure visibility**
- Baseline mismatches bubble up through the reusable workflow via `agent-bench baseline --compare` (exit codes above) and the policy gate script, so GitHub marks the job red and prints messages such as `steps_used delta 14 exceeds max_step_delta 10`.
- Artifacts (`.agent_bench/runs`, `run.json`) automatically attach for diff triage.

## GitLab CI example (separate stages)
```yaml
stages:
  - run
  - compare
  - gate

variables:
  PYTHON_VERSION: "3.12"

run_agent:
  stage: run
  image: python:$PYTHON_VERSION
  script:
    - pip install -e .[dev]
    - tracecore run --agent agents/chain_agent.py --task rate_limited_chain@1 --seed 0 > run.json
  artifacts:
    paths:
      - run.json
      - .agent_bench/runs/

compare_baseline:
  stage: compare
  image: python:$PYTHON_VERSION
  needs: [run_agent]
  script:
    - pip install -e .[dev]
    - tracecore baseline --compare .agent_bench/baselines/rate_limited_chain_chain_agent.json $(python -c "import json;print(json.load(open('run.json'))['run_id'])") --format text

policy_gates:
  stage: gate
  image: python:$PYTHON_VERSION
  needs: [compare_baseline]
  script:
    - pip install -e .[dev]
    - python scripts/policy_gate.py --run-json run.json --baseline .agent_bench/baselines/rate_limited_chain_chain_agent.json --max-steps 180 --max-step-delta 10
```

**Failure visibility**
- `agent-bench baseline --compare` sets the job status (`0/1/2`). Keep `--format text` so failures show up in job logs.
- The gate step can emit explicit `Policy gate failures:` messages (mirror the reusable workflow’s Python snippet) and exit non-zero to stop the pipeline.
- Artifacts from the `run_agent` job remain available for download from later stages.

## Internal tooling / scheduler sketch
1. **Schedule cadence** – cron or orchestrator triggers (e.g., hourly) call a small runner script.
2. **Runner script**
   ```bash
   tracecore run --agent agents/chain_agent.py --task rate_limited_chain@1 --seed "$TRACECORE_SEED" > run.json
   RUN_ID=$(python -c "import json;print(json.load(open('run.json'))['run_id'])")
   tracecore baseline --compare "$TRACECORE_BASELINE" "$RUN_ID" --format json > compare.json || echo "Compare exit code: $?"
   python scripts/policy_gate.py --run-json run.json --baseline "$TRACECORE_BASELINE" --max-steps 180 --max-step-delta 10
   ```
   Note: Legacy alias `agent-bench` remains optional for backwards compatibility.
3. **Evidence capture** – persist `.agent_bench/runs/${RUN_ID}.json`, `run.json`, and `compare.json` to your internal evidence store (S3, artifact bucket) along with a metadata row `{run_id, task_ref, agent_path, timestamp}`.
4. **Alerting** – wire the policy gate script’s exit code into your orchestrator’s alert channel (PagerDuty, Slack) so failures are noisy, mirroring the GitHub/GitLab examples.

This keeps TraceCore integrations consistent across CI providers and internal automation without duplicating logic.
