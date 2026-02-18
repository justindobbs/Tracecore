# Record Mode: Sealed Execution Contracts

> **Status: Future Vision — Not Yet Implemented**
>
> This document describes the planned `--record` / `--replay` / `--strict` execution model for
> TraceCore. **None of these CLI flags exist in the current release.** The current harness already
> produces replayable run artifacts (see `agent-bench run --replay <run_id>`) and deterministic
> regression tests (`tests/test_determinism.py`), but the formal sealed-contract record mode
> described below is a roadmap item.
>
> Do not rely on the commands or file layouts in this document for production use. When record mode
> ships, this banner will be removed and the document will be updated to reflect the implemented
> interface.

Record mode is the make-or-break feature for TraceCore's deterministic episode runtime. It captures the agent–environment interaction surface once, audits it, and freezes it into a replayable execution substrate.

Not logging. Not mocking. Not golden outputs. A sealed execution contract.

## Mental model

Record mode is a one-time, audited capture of the agent–environment interaction surface that later becomes a frozen, replayable execution substrate.

## Execution modes

TraceCore has exactly three modes—no ambiguity.

| Mode   | Purpose                    | Allowed side effects              |
| ------ | -------------------------- | --------------------------------- |
| record | Capture a canonical run    | External IO allowed but audited   |
| replay | Deterministic regression   | No external IO                    |
| strict | CI enforcement             | Replay-only + invariants          |

Rule: CI is never allowed to run record.

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

1. **Task enters record mode**
   ```sh
   tracecore run ticker_lookup_v1 --record
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

## Replay mode (default local dev)

```sh
tracecore run ticker_lookup_v1
```

Replay rules:
- No network
- No filesystem writes
- No randomness
- Tool outputs must match snapshots
- Step order must match snapshots

If the agent deviates:
```
ReplayMismatch:
  step 2 tool output hash mismatch
```

## Strict mode (CI)

```sh
tracecore test --strict
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

- **First time (human-in-the-loop):** `tracecore run ticker_lookup_v1 --record` then `git commit baselines/ticker_lookup_v1`
- **Everyday dev:** `tracecore run ticker_lookup_v1`
- **CI gate:** `tracecore test --strict`

No re-records in CI. No silent updates. No flakiness.

## When re-recording is allowed

Only when intentionally changing behavior:
- Task version bump
- Tool contract change
- Validator change
- Known environment update

Always explicit:
```sh
tracecore run ticker_lookup_v2 --record
```

Old baselines remain intact.

## Why this is hard (and valuable)

Most systems log after the fact, mix record and replay, allow silent drift, and blur test vs benchmark. TraceCore separates capture from enforcement, makes recording explicit and auditable, treats the environment as part of the contract, and enables long-lived reliability guarantees.

## Key insight

Record mode is not about truth; it is about freezing expectations. Once frozen, everything else becomes measurable for the deterministic episode runtime.
