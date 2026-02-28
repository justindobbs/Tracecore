# What's New in TraceCore v1.0

TraceCore v1.0 is the first stable release of the Deterministic Episode Runtime. Every feature shipped under the v0.9.x series was building toward this: a frozen specification, a hardened runner, and enough operational tooling to take TraceCore from "interesting prototype" to a reliable foundation for CI-grade agent evaluation.

This document walks through the headline changes. See [`CHANGELOG.md`](../CHANGELOG.md) for the full diff and [`spec/tracecore-spec-v1.0.md`](../spec/tracecore-spec-v1.0.md) for the normative text.

---

## The `tracecore` command is now first-class

Previously the CLI was `agent-bench` only. Starting with v1.0, `tracecore` is a proper installed entry point:

```bash
pip install tracecore
tracecore run pairing log_stream_monitor --seed 7 --strict-spec
tracecore version
```

`agent-bench` still works as a legacy alias — nothing breaks. But new docs, examples, and the spec all use `tracecore`.

---

## Spec v1.0 — provisional language is now normative

[`spec/tracecore-spec-v1.0.md`](../spec/tracecore-spec-v1.0.md) promotes everything in v0.1 from "SHOULD" to "MUST" and adds two new sections:

- **Section 6: Batch Execution Requirements** — normative rules for parallel episode runners (worker isolation, timeout semantics, aggregate artifact format).
- **Section 10: Changelog from v0.1** — machine-readable record of every breaking and additive change.

The companion schema [`spec/artifact-schema-v1.0.json`](../spec/artifact-schema-v1.0.json) adds `wall_clock_elapsed_s` as a required field. Every run artifact emitted by v1.0 declares `"spec_version": "tracecore-spec-v1.0"`.

Alternative runtimes (Rust, Go, JS, etc.) that want to claim spec conformance must implement v1.0 and report the correct `spec_version` in every artifact.

---

## `wall_clock_elapsed_s` — wall time is now a first-class artifact field

Every run artifact now records how long the episode actually took:

```json
{
  "wall_clock_elapsed_s": 4.217,
  "spec_version": "tracecore-spec-v1.0",
  ...
}
```

The field is excluded from `artifact_hash` computation (it's volatile across machines), but it is validated by `--strict-spec` and required by the v1.0 schema. This makes budget utilisation dashboards and MTTR analysis possible without post-hoc log scraping.

---

## Parallel batch execution

Run a full suite of episodes concurrently in one command:

```bash
tracecore run batch --workers 4 --timeout 120 --strict-spec
```

Or point at a JSON file of `(agent, task_ref, seed)` triples:

```bash
tracecore run batch --batch-file my_suite.json --workers 8
```

Under the hood, each job runs in a **clean spawned subprocess** (`multiprocessing` spawn context) so there is zero state leakage between workers. Timed-out jobs produce a proper `failure_type=timeout` artifact rather than a silent hang.

The summary printed at the end includes:

- total / passed / failed counts
- P50 and P95 wall-clock time
- per-job failure types

---

## Metrics — reproducibility rates, budget utilisation, MTTR

Three new ways to slice your run history:

### CLI

```bash
tracecore runs metrics --format table
tracecore runs metrics --task log_stream_monitor@1 --format json
tracecore runs mttr --agent agents/toy_agent.py --task filesystem_hidden_config@1
```

### REST API

```
GET /api/metrics
GET /api/metrics?task=log_stream_monitor@1&agent=agents/toy_agent.py&limit=100
```

### Dashboard

Navigate to `/metrics` (or click **Metrics** in the nav bar) for a live view of:

- reproducibility rate per task/agent pair (colour-coded progress bars)
- steps and tool-call budget P50/P95 vs. ceiling
- failure taxonomy breakdown
- mean time to recovery

---

## Process isolation for batch workers

`agent_bench/runner/isolation.py` was a 5-line stub in v0.9. It is now a real implementation:

- each batch worker forks into a fresh `spawn`-context subprocess
- the child's working directory and `sys.path` are set explicitly
- the parent enforces a per-job wall-clock timeout and kills the child on overflow

This makes `tracecore run batch` safe to run in CI without leaking environment state between jobs.

---

## `tracecore version`

```bash
$ tracecore version
runtime: 1.0.0  spec: tracecore-spec-v1.0
```

Useful for CI log provenance — pin the exact runtime + spec combination that produced a set of artifacts.

---

## Dashboard fixes

Two long-standing dashboard bugs are fixed in v1.0:

- **Run button did nothing** — the `POST /run` handler called the blocking `runner.run()` directly inside an `async` FastAPI handler, freezing the entire event loop. Fixed by offloading to `asyncio.run_in_executor`.
- **`__init__.py` in agent dropdown** — the local `agents/` glob now filters Python package init files, matching the bundled-fallback behaviour that was already correct.

---

## Upgrade guide

```bash
pip install --upgrade tracecore
tracecore version   # should print: runtime: 1.0.0  spec: tracecore-spec-v1.0
```

**Breaking changes:** none for CLI users. The only schema change is the addition of `wall_clock_elapsed_s` as a required field — existing artifacts produced by v0.9.x will fail `--strict-spec` validation against the v1.0 schema, but the runner falls back to `artifact-schema-v0.1.json` for older artifacts automatically.

**If you wrote tests that assert `spec_version == "tracecore-spec-v0.1"`**, update them to `"tracecore-spec-v1.0"`.

---

## What's next

Phase 4 is complete. The focus for post-v1.0 work is:

- **Trace diff CLI** (`tracecore diff run_a run_b`) with OTLP-compatible export
- **Signing / attestation** (Cosign) for evidence bundles — unlocked now that schemas are stable
- **Richer failure taxonomy UX** — surface termination reason + failure type together in the dashboard by default

See [`roadmap.md`](../roadmap.md) for the full picture.
