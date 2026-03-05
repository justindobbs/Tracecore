# multi_role_escalation@1

## Overview
Coordinate a two-stage incident escalation where an analyst token and a manager
acknowledgment must be combined using the documented format. Agents must parse
multiple signal files, respect the specified token order, and only emit the
final `ESCALATION_CODE` once both stages are confirmed.

## Mechanics
- Read `/app/README.md` to learn the escalation contract and discover signal
  paths under the `Signals` section.
- Inspect `/app/conversations/analyst.log` to recover the deterministic
  `ANALYST_TOKEN`.
- Inspect `/app/conversations/manager_ack.txt` to confirm the
  `MANAGER_TOKEN`.
- Consult `/app/incidents/final.md` for `FINAL_FORMAT`, which dictates how the
  two tokens must be combined.
- Submit `ESCALATION_CODE=<value>` via `set_output` only after filling the
  format template with the validated tokens.

## Actions
- `list_dir(path: str)`
- `read_file(path: str)`
- `extract_value(content: str, key: str)`
- `set_output(key: str, value: str)`

## Significance
Future TraceCore scenarios expect multi-role orchestration (Recon + Executor,
Planner + Doer, etc.). This task is intentionally simple but requires agents to
collect signals from multiple sources and honor an explicit combination
contract. It pairs well with the `MultiRoleOpsAgent` reference implementation
that demonstrates the new orchestration harness.
