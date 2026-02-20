# Record Mode: Sealed Execution Contracts

> **Status: Partially Implemented (v0.7.0)**
>
> Replay enforcement (`--replay-bundle`) and strict mode (`--strict`) are now implemented.
> The `--record` flag (first-time capture with audited sandbox) remains a roadmap item.
> The baseline bundle format (`manifest.json`, `tool_calls.jsonl`, `validator.json`, `integrity.sha256`)
> is stable and documented in `docs/trace_artifacts.md`.

Record mode is the make-or-break feature for TraceCore's deterministic episode runtime. It captures the agent–environment interaction surface once, audits it, and freezes it into a replayable execution substrate.

Not logging. Not mocking. Not golden outputs. A sealed execution contract.

## Mental model

Record mode is a one-time, audited capture of the agent–environment interaction surface that later becomes a frozen, replayable execution substrate.

## Execution modes

TraceCore has exactly three modes—no ambiguity.

| Mode   | Purpose                    | Allowed side effects              | Status         |
| ------ | -------------------------- | --------------------------------- | -------------- |
| record | Capture a canonical run    | External IO allowed but audited   | Roadmap        |
| replay | Deterministic regression   | No external IO                    | **Implemented** |
| strict | CI enforcement             | Replay-only + invariants          | **Implemented** |

Rule: CI is never allowed to run record.

## CLI (implemented)

```sh
# Write a baseline bundle from the most recent run:
agent-bench baseline --agent agents/toy_agent.py --task filesystem_hidden_config@1 --bundle

# Re-run and verify the trace matches the bundle:
agent-bench run --agent agents/toy_agent.py --task filesystem_hidden_config@1 --replay-bundle .agent_bench/baselines/<run_id>

# Strict mode — replay + budget must not exceed baseline:
agent-bench run --agent agents/toy_agent.py --task filesystem_hidden_config@1 --replay-bundle .agent_bench/baselines/<run_id> --strict

# Verify bundle integrity without re-running:
agent-bench bundle verify .agent_bench/baselines/<run_id>
agent-bench bundle verify .agent_bench/baselines/<run_id> --format json
```

## What gets recorded

Record mode captures boundary interactions, not internals.

**Recorded artifacts**

- Tool invocation inputs (agent intent)
- Tool invocation outputs (environment response)
- Step ordering (control-flow determinism)
- Budget counters (resource semantics)
- Validator outcome (ground truth)
- Run hash (integrity & tamper detection)

**Explicitly not recorded**

- LLM tokens
- Chain-of-thought
- Internal agent memory
- Framework-specific internals

TraceCore records what the agent does, not how it thinks.

## Execution flow

1. **Task enters record mode** *(roadmap)*
   ```sh
   agent-bench run --agent agents/my_agent.py --task ticker_lookup_v1@1 --record
   ```
   - Task is not frozen yet
   - No existing baseline exists
   - Explicit human intent (`--record` required)

2. **Sandbox opens with audited permissions**

   Allowed only during record:
   - Network (declared domains only)
   - File IO (declared paths only)
   - Time (fixed clock abstraction)
   - Randomness (seeded + captured)

   Example sandbox policy:
   ```toml
   [sandbox]
   network.allow = ["duckduckgo.com", "marketwatch.com"]
   filesystem.allow = ["./tmp"]
   clock.mode = "fixed"
   ```

   Any undeclared access = hard failure, even in record mode.

3. **Tool calls are intercepted and snapshotted**

   Each tool invocation produces a snapshot:
   ```json
   {
     "tool": "search_ticker",
     "input": {"company_name": "Amazon"},
     "output": {"ticker": "AMZN"},
     "step": 2,
     "timestamp": 1700001234,
     "hash": "sha256:abc123"
   }
   ```

   Properties:
   - Inputs and outputs are schema-validated
   - Output hash is immutable
   - Ordering is preserved

4. **Determinism is measured during recording**

   TraceCore immediately replays the same run:
   - Pass 1 → capture
   - Pass 2 → replay capture

   If outputs differ: `RecordRejected: NonDeterministic`

   This prevents freezing unstable behavior.

5. **Validator executes** (after capture)

   Example:
   ```yaml
   validator:
     type: exact_json_match
     expected:
       ticker: "AMZN"
   ```

   Result is recorded as:
   ```json
   {"validator": "exact_json_match", "passed": true}
   ```

   If the validator fails: **no baseline is created**.

6. **Baseline is sealed**

   TraceCore writes a content-addressed bundle:
   ```
   baselines/
   └── ticker_lookup_v1/
       ├── manifest.json
       ├── tool_calls.jsonl
       ├── validator.json
       ├── run_meta.json
       └── integrity.sha256
   ```

   Example manifest fields:
   ```json
   {
     "task_id": "ticker_lookup_v1",
     "seed": 42,
     "max_steps": 5,
     "tool_hashes": {"search_ticker": "sha256:..."},
     "runner_version": "0.3.1",
     "created_at": "2026-02-16"
   }
   ```

   Tampering is detectable.

## Replay mode (implemented)

```sh
agent-bench run --agent agents/my_agent.py --task filesystem_hidden_config@1 \
  --replay-bundle .agent_bench/baselines/<run_id>
```

Replay rules:
- No network
- No filesystem writes
- No randomness
- Tool outputs must match snapshots
- Step order must match snapshots

If the agent deviates, the run exits 1 and prints:
```
[REPLAY FAILED]
  step 2: result mismatch — baseline=... fresh=...
```

## Strict mode (implemented)

```sh
agent-bench run --agent agents/my_agent.py --task filesystem_hidden_config@1 \
  --replay-bundle .agent_bench/baselines/<run_id> --strict
```

Strict adds:
- Budget must match exactly
- Step count must not exceed baseline
- No new tools
- No schema drift
- No non-determinism tolerated

Strict mode answers: "Did anything operationally meaningful change?"

## Why record mode (vs fixtures/mocks)

- Agents choose when to call tools; control flow matters
- Budget consumption and partial failures matter
- Ordering matters
- Record mode captures the agent–environment protocol, not just responses

## Developer workflow

- **First time (human-in-the-loop):** run the agent, then `agent-bench baseline --bundle` to seal the bundle, then `git commit .agent_bench/baselines/<run_id>`
- **Everyday dev:** `agent-bench run --agent ... --task ... --replay-bundle <path>`
- **CI gate:** `agent-bench run --agent ... --task ... --replay-bundle <path> --strict`

No re-records in CI. No silent updates. No flakiness.

## When re-recording is allowed

Only when intentionally changing behavior:
- Task version bump
- Tool contract change
- Validator change
- Known environment update

Always explicit:
```sh
agent-bench run --agent agents/my_agent.py --task ticker_lookup_v2@1 --record
```

Old baselines remain intact.

## Why this is hard (and valuable)

Most systems log after the fact, mix record and replay, allow silent drift, and blur test vs benchmark. TraceCore separates capture from enforcement, makes recording explicit and auditable, treats the environment as part of the contract, and enables long-lived reliability guarantees.

## Key insight

Record mode is not about truth; it is about freezing expectations. Once frozen, everything else becomes measurable for the deterministic episode runtime.
