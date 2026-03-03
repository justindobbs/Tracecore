# Record Mode: Sealed Execution Contracts

> **Status: Implemented**
>
> All three modes are implemented. `--record` runs the agent, verifies determinism by re-running,
> and seals a baseline bundle — rejecting non-deterministic episodes before they can be committed.
> `--replay-bundle` and `--strict` enforce the sealed contract in CI.
> Sandbox permissions are now required in deterministic task manifests and are enforced for task
> filesystem access at runtime. Network allowlists are available to actions via
> `env.require_network(host)` when a task needs outbound access.
> Record mode now audits filesystem + network IO per step and persists those audit entries in
> `tool_calls.jsonl` for replay/strict enforcement. Baseline bundles also mirror the task
> sandbox allowlists in `manifest.json` (see `docs/trace_artifacts.md`).

Record mode is the make-or-break feature for TraceCore's deterministic episode runtime. It captures the agent–environment interaction surface once, audits it, and freezes it into a replayable execution substrate.

Not logging. Not mocking. Not golden outputs. A sealed execution contract.

## Mental model

Record mode is a one-time, audited capture of the agent–environment interaction surface that later becomes a frozen, replayable execution substrate.

## Execution modes

TraceCore has exactly three modes—no ambiguity.

| Mode   | Purpose                    | Allowed side effects                                 | Status         |
| ------ | -------------------------- | ---------------------------------------------------- | -------------- |
| record | Capture a canonical run    | External IO allowed; audited against allowlists      | **Implemented** |
| replay | Deterministic regression   | Audited against allowlists                           | **Implemented** |
| strict | CI enforcement             | Replay-only + invariants + audited allowlists        | **Implemented** |

Rule: CI is never allowed to run record.

## CLI

```sh
# Record: run the agent, verify determinism, seal a bundle:
tracecore run --agent agents/toy_agent.py --task filesystem_hidden_config@1 --record

# Verify bundle integrity without re-running:
tracecore bundle verify .agent_bench/baselines/<run_id>

# Replay: re-run and verify the trace matches the bundle:
tracecore run --agent agents/toy_agent.py --task filesystem_hidden_config@1 --replay-bundle .agent_bench/baselines/<run_id>

# Strict mode — replay + budget must not exceed baseline:
tracecore run --agent agents/toy_agent.py --task filesystem_hidden_config@1 --replay-bundle .agent_bench/baselines/<run_id> --strict
```

### Everyday iterative loop (no re-record)

Most local development does **not** require record mode. The default loop now keeps track of the
latest run/bundle via `.agent_bench/session.json`, so you no longer have to copy-paste run IDs:

```sh
# 1. Run the agent
tracecore run --agent agents/my_agent.py --task my_task@1 --seed 0

# (CLI prints suggested next steps)

# 2. Verify the latest run/bundle pair
tracecore verify               # defaults to the latest successful run

# 3. Seal a bundle when you're satisfied
tracecore bundle seal          # defaults to the latest successful run

# 4. Inspect recent bundles / integrity state
tracecore bundle status
```

- `verify` will automatically grab the most recent bundle (if present) and run replay/strict checks.
- `bundle seal` writes `.agent_bench/baselines/<run_id>/` and updates the session pointer so the next
  `verify` run knows which artifacts to compare.
- `bundle status` surfaces OK/FAIL for everything under `.agent_bench/baselines/` so you can purge or
  re-seal as needed.
- Add `--json` to `verify`/`bundle seal`/`bundle status` to integrate with scripts or CI dashboards.

Record mode slots in **only** when you intentionally need a fresh canonical baseline. Most days you
stay in the run → verify → bundle loop above, then flip CI into `--replay-bundle`/`--strict` to guard
regressions.

### Optional record and ledger usage

- Use `--record` (see section below) **only** when the task contract changes and you intentionally
  want to capture a new baseline. Otherwise, rely on normal runs so the existing bundles stay valid.
- After sealing a bundle you can optionally sign + register it in the TraceCore Ledger:

  ```sh
  tracecore bundle seal --latest --sign --key keys/tracecore_ed25519.pem
  tracecore ledger publish --bundle .agent_bench/baselines/<run_id>
  tracecore ledger show --id <entry_id>
  ```

  Ledger usage is additive: unsigned local bundles still work for replay/strict, but signing/publishing
  gives you provenance and tamper-proof audit trails when you need them.

## What gets recorded

Record mode captures boundary interactions, not internals.

**Recorded artifacts**

- Tool invocation inputs (agent intent)
- Tool invocation outputs (environment response)
- Step ordering (control-flow determinism)
- Budget counters (resource semantics)
- IO audit entries (filesystem/network access)
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
   tracecore run --agent agents/my_agent.py --task my_task@1 --record
   ```
   - Explicit human intent (`--record` required — not allowed in CI)
   - No existing baseline required

2. **First run executes; bundle is sealed on success**

   The agent runs normally. If the run succeeds, a baseline bundle is written to
   `.agent_bench/baselines/<run_id>/`. A failed run is rejected immediately:
   ```
   [RECORD REJECTED] run did not succeed — only successful runs can be sealed
   ```

3. **Second run verifies determinism**

   The agent runs again with the same seed. The two traces are compared step-by-step
   (action type, args, result, outcome). If they diverge, the bundle is deleted:
   ```
   [RECORD FAILED: NonDeterministic]
     step 3: action mismatch — run1=... run2=...
   [RECORD] bundle deleted: .agent_bench/baselines/<run_id>
   ```

4. **Bundle is sealed**

   On success:
   ```
   [RECORD OK] bundle sealed: .agent_bench/baselines/<run_id>
     commit with: git add .agent_bench/baselines/<run_id>
   ```

   Bundle layout:
   ```
   .agent_bench/baselines/<run_id>/
       ├── manifest.json       # run metadata
       ├── tool_calls.jsonl    # one line per trace step
       ├── validator.json      # final validation snapshot
       └── integrity.sha256    # SHA-256 hashes of the above
   ```

   Tampering is detectable via `tracecore bundle verify <path>`.

   **Sandbox permissions** (declared network/filesystem domains) are required in deterministic
   task manifests and enforced at runtime. Record mode captures per-step IO audit entries and
   replays/strict enforce that the live IO trace exactly matches the bundle.

## Replay mode

```sh
tracecore run --agent agents/my_agent.py --task filesystem_hidden_config@1 \
  --replay-bundle .agent_bench/baselines/<run_id>
```

Replay rules (all enforced):
- `success` must match baseline
- `termination_reason` must match baseline
- `failure_type` must match baseline
- Every step's `action` (type + args) must match
- Every step's `result` must match
- Step count must match

If the trace diverges, exits 1 and prints exactly what changed:
```
[REPLAY FAILED]
  step 2: result mismatch — baseline=... fresh=...
```

## Strict mode

```sh
agent-bench run --agent agents/my_agent.py --task filesystem_hidden_config@1 \
  --replay-bundle .agent_bench/baselines/<run_id> --strict
```

Strict adds budget invariants on top of replay:
- `steps_used` must not exceed baseline
- `tool_calls_used` must not exceed baseline

Strict mode answers: "Did anything operationally meaningful change?"

## Why record mode (vs fixtures/mocks)

- Agents choose when to call tools; control flow matters
- Budget consumption and partial failures matter
- Ordering matters
- Record mode captures the agent–environment protocol, not just responses

## Developer workflow

```sh
# 1. Seal a baseline (human-in-the-loop, once)
tracecore run --agent agents/my_agent.py --task my_task@1 --record

# 2. Commit the bundle
git add .agent_bench/baselines/<run_id>
git commit -m "seal: my_agent baseline for my_task@1"

# 3. Verify integrity at any time
tracecore bundle verify .agent_bench/baselines/<run_id>

# 4. CI gate on every PR
tracecore run --agent agents/my_agent.py --task my_task@1 \
  --replay-bundle .agent_bench/baselines/<run_id> --strict
```

No re-records in CI. No silent updates. No flakiness.

## When re-recording is allowed

Only when intentionally changing behavior:
- Task version bump
- Tool contract change
- Validator change
- Known environment update

Always explicit:
```sh
tracecore run --agent agents/my_agent.py --task my_task@2 --record
```

Old baselines remain intact.

## Why this is hard (and valuable)

Most systems log after the fact, mix record and replay, allow silent drift, and blur test vs benchmark. TraceCore separates capture from enforcement, makes recording explicit and auditable, treats the environment as part of the contract, and enables long-lived reliability guarantees.

## Key insight

Record mode is not about truth; it is about freezing expectations. Once frozen, everything else becomes measurable for the deterministic episode runtime.
