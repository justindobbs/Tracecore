---
description: End-to-end runbook_verifier workflow (record → replay)
---

# Runbook Verifier Tutorial

This walkthrough shows how to seal the `runbook_verifier@1` deterministic task into a
baseline bundle and enforce it in CI via `--replay-bundle --strict`.

## Prerequisites

- TraceCore benchmark repo with Python 3.12 environment activated.
- Bundled task `runbook_verifier@1` (already in `tasks/`).
- Reference agent `agents/runbook_verifier_agent.py` or your own compliant agent.
- Clean working tree (commit unrelated changes first).

## 1. Validate the task manifest

Before recording, confirm the task loads cleanly:

```sh
agent-bench tasks validate --path tasks/runbook_verifier
```

Expected: `{"valid": true, "errors": []}`

## 2. Record a baseline bundle locally

Run the deterministic agent once with `--record`. This executes the task,
verifies determinism (second run), and seals the bundle under
`.agent_bench/baselines/runbook_verifier@1/`.

```sh
agent-bench run \
  --agent agents/runbook_verifier_agent.py \
  --task runbook_verifier@1 \
  --seed 0 \
  --record
```

Expected tail output:

```
✔ SUCCESS  runbook_verifier@1  |  steps: 10  tool_calls: 10
[RECORD OK] bundle sealed: .agent_bench\baselines\runbook_verifier@1
```

If the run fails (budget exhaustion, validator error), fix the agent or task
inputs before retrying—only successful runs can be sealed.

## 3. Commit the sealed bundle

```sh
git add .agent_bench/baselines/runbook_verifier@1
git commit -m "seal: runbook_verifier@1 baseline"
```

The committed directory contains `manifest.json`, `tool_calls.jsonl`,
`validator.json`, and `integrity.sha256`. Treat it as immutable history: bump the
run ID only when deliberately re-recording.

## 4. Enforce replay/strict in CI

### GitHub Actions (copy from `ci/templates/github-record-replay.yml`)

Set the env vars to match your recording parameters:

```yaml
jobs:
  replay_strict_gate:
    runs-on: ubuntu-latest
    env:
      AGENT: "agents/runbook_verifier_agent.py"          # customize per project
      TASK: "runbook_verifier@1"                          # must match recorded task
      SEED: "0"                                           # must match recorded seed
      BUNDLE: ".agent_bench/baselines/runbook_verifier@1" # committed bundle path
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: |
          python -m pip install --upgrade pip
          pip install -e .[dev]
      - name: Run replay gate (strict)
        run: |
          agent-bench run --agent "$AGENT" --task "$TASK" --seed "$SEED" \
            --replay-bundle "$BUNDLE" --strict 2>&1 | tee run.log
      - name: Upload run log
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: run-log-${{ github.run_id }}
          path: run.log
```

Failures (trace divergence, validator error) surface as CI job failures with
`run.log` artifact for debugging.

### GitLab CI (copy from `ci/templates/gitlab-record-replay.yml`)

Define these variables in your project or pipeline settings:

```yaml
variables:
  AGENT_PATH: "agents/runbook_verifier_agent.py"          # customize per project
  TASK_REF: "runbook_verifier@1"                          # must match recorded task
  RUN_SEED: "0"                                           # must match recorded seed
  BUNDLE_PATH: ".agent_bench/baselines/runbook_verifier@1" # committed bundle path

replay_strict_gate:
  stage: gate
  image: python:3.12
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
  script:
    - pip install -e .[dev]
    - agent-bench run --agent "$AGENT_PATH" --task "$TASK_REF" --seed "$RUN_SEED" \
        --replay-bundle "$BUNDLE_PATH" --strict 2>&1 | tee run.log
  artifacts:
    paths:
      - run.log
    when: always
```

## 5. Re-recording flow

When you intentionally update the task or agent:

1. Bump the bundle by rerunning the `--record` command.
2. Review `tool_calls.jsonl` to ensure the checksum or handoff logic changed as
   expected.
3. Commit both the updated task code and the new bundle in the same change set.
4. CI replay/strict should now pass using the new baseline.

## 6. Troubleshooting tips

- **Replay mismatch**: run `agent-bench run --agent ... --task ... --seed 0` locally
  without `--record` to inspect the failing `run.json` under `.agent_bench/runs/`.
- **Missing checksum**: confirm the agent calls `set_output("RUNBOOK_CHECKSUM", ...)`.
- **Schema drift**: see `docs/contract.md` for compatibility guarantees before
  altering trace or bundle formats.

This completes the end-to-end workflow for publishing and enforcing
`runbook_verifier@1`. Repeat the same pattern for additional deterministic
operations tasks.
