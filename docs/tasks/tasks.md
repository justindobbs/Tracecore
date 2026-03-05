---
description: Task catalog and significance
---

# Task Catalog

Use this catalog to understand what each bundled task measures, how it is wired, and why it matters to TraceCore. Every task entry links to its source directory for deeper implementation notes.

## Registry & plugin workflow

- `tasks/registry.json` is the manifest that keeps README/SPEC_FREEZE/docs in sync. When you add or bump a bundled task, update this file so downstream tooling can discover it.
- Each task directory includes a `task.toml` manifest (see [`docs/task_manifest.md`](task_manifest.md)) describing budgets, entrypoints, and deterministic behavior.
- External task packages can register via the `agent_bench.tasks` entry-point group. See [`docs/task_plugin_template.md`](task_plugin_template.md) for a starter layout, entry-point snippet, and `register()` helper contract.
- The loader merges bundled manifest rows + plugin descriptors, so `agent-bench run --task your_plugin_task@1` works once the plugin package is installed.

## filesystem_hidden_config@1
- **Suite**: filesystem · **Deterministic**: ✅ · **Path**: [`tasks/filesystem_hidden_config/`](../tasks/filesystem_hidden_config/)
- **Core idea**: forces agents to plan cautious filesystem exploration to recover `API_KEY` without brute-force traversal.
- **Skills stressed**:
  - Stateful search across nested directories.
  - Budget-aware exploration vs. repeated reads.
  - Validating when a clue (config file) resolves the goal.
- **Why it matters**: mirrors classic "find config secret" incidents where LLM agents must persist state, avoid loops, and stop once the secret is located.

## rate_limited_api@1
- **Suite**: api · **Deterministic**: ✅ · **Path**: [`tasks/rate_limited_api/`](../tasks/rate_limited_api/)
- **Core idea**: single-endpoint API that enforces strict quotas and transient failures; agents must respect `retry_after` windows.
- **Skills stressed**:
  - Differentiating `rate_limited` vs. `temporary_failure` vs. fatal errors.
  - Implementing exponential/backoff-style waiting with the `wait` action.
  - Submitting the token through `set_output` only when confirmed.
- **Why it matters**: probes whether an agent can follow API etiquette under pressure—no handshake yet, but lots of budget management.

## rate_limited_chain@1
- **Suite**: api · **Deterministic**: ✅ · **Path**: [`tasks/rate_limited_chain/`](../tasks/rate_limited_chain/)
- **Core idea**: extends the previous API with a handshake template and chained endpoints that expire; combines instruction following with rate limits.
- **Skills stressed**:
  - Parsing README/templates to craft the handshake response.
  - Tracking `handshake_id` lifetimes and retry windows simultaneously.
  - Differentiating fatal vs. transient API responses to know when to restart.
- **Why it matters**: captures real-world auth flows (OAuth/device codes) where skipping handshake logic bricks the session.

## deterministic_rate_service@1
- **Suite**: api · **Deterministic**: ✅ · **Path**: [`tasks/deterministic_rate_service/`](../tasks/deterministic_rate_service/)
- **Core idea**: deterministic yet unforgiving service combining handshake confirmation, required payload templates, rate limiting, and a guaranteed transient hiccup.
- **Skills stressed**:
  - Maintaining service state (virtual clock, retry budget, history).
  - Distinguishing `rate_limited`, `temporary_failure`, `bad_request`, `invalid_handshake`, and escalating appropriately.
  - Recovering from fatal payload errors by restarting the flow automatically.
- **Why it matters**: this is TraceCore’s "depth" scenario—agents must orchestrate multi-step APIs without over-spending limited tool calls, which is representative of production integration incidents.

## log_alert_triage@1
- **Suite**: operations · **Deterministic**: ✅ · **Path**: [`tasks/log_alert_triage/`](../tasks/log_alert_triage/)
- **Core idea**: walk deterministic log artifacts and recover the final `ALERT_CODE` used for escalation.
- **Skills stressed**:
  - Parsing operational logs for actionable signals.
  - Following breadcrumbs across multiple files.
  - Avoiding unnecessary reads once the alert code is found.
- **Why it matters**: mirrors real-world log triage where the last error line controls escalation playbooks.

## config_drift_remediation@1
- **Suite**: operations · **Deterministic**: ✅ · **Path**: [`tasks/config_drift_remediation/`](../tasks/config_drift_remediation/)
- **Core idea**: compare desired vs. live configuration and output the exact remediation patch line.
- **Skills stressed**:
  - Differencing structured configs.
  - Isolating the single drifted setting under budget pressure.
  - Emitting a precise corrective change without modifying files.
- **Why it matters**: captures high-signal config drift investigations that production agents must handle cleanly.

## incident_recovery_chain@1
- **Suite**: operations · **Deterministic**: ✅ · **Path**: [`tasks/incident_recovery_chain/`](../tasks/incident_recovery_chain/)
- **Core idea**: follow a deterministic recovery handoff chain to extract the final `RECOVERY_TOKEN`.
- **Skills stressed**:
  - Tracking sequential handoffs across incident notes.
  - Preserving context across multi-step recovery procedures.
  - Stopping once the authoritative token is located.
- **Why it matters**: models recovery runbooks where skipping a step yields bad remediation.

## log_stream_monitor@1
- **Suite**: operations · **Deterministic**: ✅ · **Path**: [`tasks/log_stream_monitor/`](../tasks/log_stream_monitor/)
- **Core idea**: poll a seeded, paginated log stream across multiple pages, filter out `INFO`/`WARN` noise, and emit the `STREAM_CODE` embedded in the first `CRITICAL` entry.
- **Skills stressed**:
  - Cursor-based pagination without over-fetching.
  - Signal/noise discrimination across a multi-page stream.
  - Stopping immediately once the trigger condition is met.
- **Why it matters**: mirrors production monitoring loops where agents must watch a live stream, ignore routine events, and fire exactly once on a critical signal — without exhausting tool-call budgets on noise.
- **Quick start**: `agent-bench run pairing log_stream_monitor`

## runbook_verifier@1
- **Suite**: operations · **Deterministic**: ✅ · **Path**: [`tasks/runbook_verifier/`](../tasks/runbook_verifier/)
- **Core idea**: verify that every incident runbook phase executed in order and emit the `RUNBOOK_CHECKSUM` combining phase codes + ACK + handoff token.
- **Skills stressed**:
  - Stitching multiple artifacts (README, index, per-phase files, timeline, handoff) into a single deterministic output.
  - Maintaining strict ordering under limited tool-call budgets.
  - Detecting incomplete phase data before emitting results.
- **Why it matters**: models the real-world audit workflow where operators must prove each mitigation phase ran before handoff, with zero tolerance for missing steps.

## sandboxed_code_auditor@1
- **Suite**: operations · **Deterministic**: ✅ · **Path**: [`tasks/sandboxed_code_auditor/`](../tasks/sandboxed_code_auditor/)
- **Core idea**: audit a sandbox runtime sample to locate a legacy bypass `ISSUE_ID` and analyzer `AUDIT_CODE`, then emit `ISSUE_ID|AUDIT_CODE` via `SANDBOX_AUDIT_TOKEN`.
- **Skills stressed**:
  - Reading scoped documentation to learn the audit output contract.
  - Inspecting source code and analyzer logs under a strict filesystem sandbox.
  - Combining multiple findings into a structured output while respecting budgets.
- **Why it matters**: sandbox regressions are high-risk; this scenario trains agents to follow deterministic audit steps, avoid unauthorized filesystem access, and report compliance findings in a repeatable format.

## security_incident_triage@1
- **Suite**: security · **Deterministic**: ✅ · **Path**: [`tasks/security_incident_triage/`](../tasks/security_incident_triage/)
- **Core idea**: correlate IDS logs, analyst findings, and CSIRT notes to emit the confirmed `BREACH_TOKEN` instead of a noisy intermediate indicator.
- **Skills stressed**:
  - Separating noisy indicators from confirmed breach evidence.
  - Following escalation narratives documented across multiple files.
  - Emitting the precise token only after the final validation step.
- **Why it matters**: security incidents often involve conflicting telemetry—agents must validate the canonical breach artifact before triggering expensive responses.

## customer_support_escalation@1
- **Suite**: operations · **Deterministic**: ✅ · **Path**: [`tasks/customer_support_escalation/`](../tasks/customer_support_escalation/)
- **Core idea**: synthesize ticket metadata, manager transcripts, and policy docs to emit the manager-confirmed `ESCALATION_CODE` without skipping checkpoints.
- **Skills stressed**:
  - Parsing structured ticket JSON to understand severity and routing.
  - Scanning multi-channel transcripts for the canonical confirmation line.
  - Verifying policy compliance before emitting the final code.
- **Why it matters**: escalation errors are costly; this task forces agents to respect escalation ladders and only act on validated manager approvals.

---
**Next steps**: For full implementation details, open each task's README (kept alongside the code) or read `docs/task_harness.md` for the harness contract.
