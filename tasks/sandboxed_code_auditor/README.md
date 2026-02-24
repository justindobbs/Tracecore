# sandboxed_code_auditor@1

Deterministic task that simulates an internal security review of a sandbox runtime. Agents must audit a small
codebase, identify the legacy bypass that violates the sandbox policy, and report the audit token in the requested
format.

## Objective
1. Read `/app/audit_scope.md` to learn the output contract and find the `TARGET_KEY`.
2. Inspect `src/runtime_guard.py` to capture the `ISSUE_ID` embedded in the legacy bypass comment.
3. Inspect `reports/audit.log` to capture the `AUDIT_CODE` emitted by the static analyzer.
4. Emit `ISSUE_ID|AUDIT_CODE` via `set_output` using the provided `TARGET_KEY`.

The task is deterministic and expects zero network access.
