# Spec Freeze (v0.1.0)

Agent Bench v0.1.0 freezes the following surfaces so results remain reproducible:

| Task | Suite | Version | Notes |
|------|-------|---------|-------|
| `filesystem_hidden_config@1` | filesystem | 1 | Deterministic path discovery task |
| `rate_limited_api@1`        | api        | 1 | Classic rate-limit + retry flow |
| `rate_limited_chain@1`      | api        | 1 | Multi-step "pain" task (handshake + rate limit) |

## Rules
1. **Task directories are immutable** once frozen. Any behavioral change requires bumping the `version` field and documenting the change in this file.
2. **Harness APIs** (`Environment`, runner budgets, result schema) must remain backward compatible. Additive fields are allowed; breaking removals require a new major tag and changelog entry.
3. **Artifacts** (`.agent_bench/runs/*.json`, `.agent_bench/baselines/*.json`) are treated as canonical evidence. Do not rewrite or delete previously published artifacts.
4. **Tests** covering frozen tasks must pass before merging. Update `tests/test_determinism.py` and task-specific scenarios whenever a bump occurs.

## Workflow for updates
1. Prototype the change under a new version (e.g., `rate_limited_chain@2`).
2. Add regression tests + documentation.
3. Update this file and the README with the new version row.
4. Export fresh baselines (`agent-bench baseline --export`) and archive the `run_id`s referenced in release notes.

Breaking any of the above requires stakeholder approval and a new minor/major release tag.
