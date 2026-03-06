# Spec Freeze (v1.0)

> **Release note (v1.1.2)** — No frozen task or spec changes were required for this release. All compatibility guarantees from the existing table remain in effect.

TraceCore v1.0 freezes the following surfaces so results remain reproducible:

**Frozen schema:** `spec/artifact-schema-v1.0.json` — all run artifacts must declare `"spec_version": "tracecore-spec-v1.0"` and include `wall_clock_elapsed_s`.  
**Frozen spec:** `spec/tracecore-spec-v1.0.md` — all provisional language promoted to normative MUST.

| Task | Suite | Version | Notes |
|------|-------|---------|-------|
| `filesystem_hidden_config@1` | filesystem | 1 | Deterministic path discovery task |
| `rate_limited_api@1`        | api        | 1 | Classic rate-limit + retry flow |
| `rate_limited_chain@1`      | api        | 1 | Multi-step "pain" task (handshake + rate limit) |
| `deterministic_rate_service@1` | api     | 1 | Deterministic handshake + payload + rate-limit service |
| `log_alert_triage@1` | operations | 1 | Deterministic log triage to recover ALERT_CODE |
| `config_drift_remediation@1` | operations | 1 | Compare desired vs. live configs and emit remediation patch |
| `incident_recovery_chain@1` | operations | 1 | Multi-stage recovery handoff culminating in RECOVERY_TOKEN |
| `log_stream_monitor@1` | operations | 1 | Poll paginated log stream, detect CRITICAL entry, emit STREAM_CODE |
| `runbook_verifier@1` | operations | 1 | Validate runbook phase execution order and emit RUNBOOK_CHECKSUM |
| `sandboxed_code_auditor@1` | operations | 1 | Audit sandbox runtime, find ISSUE_ID + AUDIT_CODE, emit combined token |
| `security_incident_triage@1` | security | 1 | Correlate incident artifacts and emit the confirmed BREACH_TOKEN |
| `customer_support_escalation@1` | operations | 1 | Follow escalation transcripts and emit the manager-confirmed ESCALATION_CODE |
| `multi_role_escalation@1` | operations | 1 | Combine analyst and manager tokens via FINAL_FORMAT for ESCALATION_CODE |

> **Internal / experimental tasks** (not part of the frozen spec; subject to change without a version bump):
>
> | Task | Suite | Notes |
> |------|-------|-------|
> | `dice_game@1` | deterministic | Internal test fixture for record mode development. Not a benchmark task. |

## Rules
1. **Task directories are immutable** once frozen. Any behavioral change requires bumping the `version` field and documenting the change in this file.
2. **Harness APIs** (`Environment`, runner budgets, result schema) must remain backward compatible. Additive fields are allowed; breaking removals require a new major tag and changelog entry.
3. **Artifacts** (`.agent_bench/runs/*.json`, `.agent_bench/baselines/*.json`) are treated as canonical evidence. Do not rewrite or delete previously published artifacts.
4. **Trust evidence bundle** must be archived for frozen releases, containing:
   - `metadata.json` with harness version, git SHA, task list, and seed policy
   - Run artifacts referenced in release notes
   - Baseline exports used for gating
5. **Tests** covering frozen tasks must pass before merging. Update `tests/test_determinism.py` and task-specific scenarios whenever a bump occurs.

## Workflow for updates
1. Prototype the change under a new version (e.g., `rate_limited_chain@2`).
2. Add regression tests + documentation.
3. Update this file and the README with the new version row.
4. Export fresh baselines (`agent-bench baseline --export`) and archive the `run_id`s referenced in release notes.
5. Produce a trust evidence bundle (zip) that includes `metadata.json`, run artifacts, and baselines.

Breaking any of the above requires stakeholder approval and a new minor/major release tag.
