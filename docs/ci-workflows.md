# CI Workflows

This document explains each GitHub Actions workflow in `.github/workflows/`, what it does, and when it runs.

---

## `ci.yml` — Core CI

**Triggers:** every push and pull request to `main`

**What it does:**

1. Runs the full unit test suite against Python 3.10 and 3.12 in parallel.
2. Builds the wheel and installs it into an isolated virtualenv.
3. Runs a battery of smoke tests against the packaged install:
   - Verifies all bundled agents are present.
   - Confirms the CLI imports correctly (`--help`).
   - Runs a real pairing (`filesystem_hidden_config`) from the packaged wheel.

**Why it's needed:** Catches import errors, missing bundled files, and broken packaging before anything else — separate from the dev-install test run.

---

## `tests.yml` — Lint + Coverage

**Triggers:** every push and pull request to `main`

**What it does:**

1. Runs `ruff check` over `agent_bench/` (linting).
2. Runs `pytest` with coverage across `agent_bench/`, `agents/`, and `tasks/`.
3. Uploads the coverage report to Codecov (if `CODECOV_TOKEN` is set).

**Why it's needed:** Enforces code style and tracks test coverage on every change. Codecov upload is optional and fails gracefully if the token is absent.

---

## `tracecore-ci.yml` — TraceCore Spec Gate + Bundle Signing

**Triggers:** push to `main` or any `v*` branch; pull requests to `main`

**What it does:**

1. **Lint + test** — same as `ci.yml` but scoped to the TraceCore spec pipeline.
2. **Spec compliance gate** — runs a reference pairing under `--strict-spec` to verify the emitted artifact satisfies the TraceCore Spec v1.0 (schema, required metadata, taxonomy).
3. **Artifact diff gate** — runs a second seed of the same pairing and diffs the two artifacts; fails if step count or tool-call count diverges beyond the allowed delta (budget regression guard).
4. **Sign bundles** *(main branch pushes only)* — uses [Cosign](https://docs.sigstore.dev/cosign/overview/) keyless OIDC signing to cryptographically sign each baseline bundle's `integrity.sha256` file. Signed artifacts (`.sig` + `.cert`) are uploaded as a workflow artifact for 90 days.

**Why it's needed:** This is the Trust Pipeline gate. It ensures every merge to `main` produces a spec-compliant, budget-stable, cryptographically signed artifact. The diff gate is the primary regression guard for determinism.

---

## `baseline-compare.yml` — Reusable Baseline Comparison

**Triggers:** manual dispatch (`workflow_dispatch`) or called by another workflow (`workflow_call`)

**Inputs:**

| Input | Description |
|---|---|
| `agent_path` | Path to the agent module |
| `task_ref` | Task reference (e.g. `filesystem_hidden_config@1`) |
| `seed` | Deterministic seed (default `0`) |
| `baseline` | Baseline run ID or path to a bundle directory |
| `require_success` | Fail if the run did not succeed (default `true`) |
| `max_steps` / `max_tool_calls` | Absolute budget ceilings |
| `max_step_delta` / `max_tool_call_delta` | Max allowed delta vs. the baseline |

**What it does:**

1. Runs the specified agent against the task.
2. Optionally verifies the baseline bundle's integrity hash.
3. Compares the run artifact to the baseline.
4. Evaluates configurable policy gates (success requirement, budget ceilings, delta limits).
5. Uploads the run artifact and `run.json` for inspection.

**Why it's needed:** A reusable building block that other workflows (e.g. `chain-agent-baseline.yml`) call to gate on specific agent/task pairings without duplicating logic.

---

## `chain-agent-baseline.yml` — Chain Agent Regression Gate

**Triggers:** every push and pull request to `main`, plus manual dispatch

**What it does:**

Calls `baseline-compare.yml` for the `chain_agent` + `rate_limited_chain@1` pairing at seed 0, comparing against the committed baseline at `.agent_bench/baselines/rate_limited_chain_chain_agent.json`.

**Why it's needed:** The `chain_agent` + `rate_limited_chain` pairing is the primary reference integration test — it exercises rate-limiting, multi-step chaining, and budget adherence end-to-end. Any regression in this pairing blocks merges.

---

## `release.yml` — Release Build & Publish

**Triggers:** push of a `v*` tag (e.g. `v0.9.1`)

**What it does:**

1. Runs unit tests as a final gate before publishing.
2. Runs reference pairings and builds baseline bundles.
3. Signs bundles with the Ed25519 release key (if `TRACECORE_SIGN_KEY` secret is set).
4. Builds the wheel and sdist with `uv build`.
5. Packages the signed `registry.json` ledger as a release artifact.
6. Creates a GitHub Release and uploads the wheel, sdist, and signed ledger.

**Why it's needed:** Automates the full release pipeline — test gate → bundle generation → signing → packaging → publishing — in a single reproducible workflow triggered by a version tag.

---

## Disabled Workflows

### `nightly.yml` *(currently disabled)*

Moved to `.github/nightly.yml.disabled`. When re-enabled (by moving back to `.github/workflows/`), it runs the full pairing suite across 5 seeds every night at 03:00 UTC, asserts reproducibility and budget health, and uploads metrics artifacts. Enable once the project is in active external use and nightly stability monitoring is warranted.
