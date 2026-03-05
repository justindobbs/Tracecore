# customer_support_escalation@1

## Overview
Resolve a deterministic enterprise support ticket by following the documented escalation ladder and emitting the `ESCALATION_CODE` acknowledged by the duty manager. Agents must parse structured ticket metadata, per-channel transcripts, and policy docs to avoid skipping required steps.

## Mechanics
- Read `/app/README.md` for the escalation contract and output requirements.
- Inspect `/app/tickets/ticket.json` for the affected service, severity, and assigned channels.
- Review `/app/conversations/` transcripts to identify the manager approval.
- Consult `/app/policies/escalation.md` to understand required acknowledgment language.
- Submit `ESCALATION_CODE=<value>` once the manager-approved code is confirmed.

## Actions
- `list_dir(path: str)`
- `read_file(path: str)`
- `read_json(path: str)`
- `extract_value(content: str, key: str)`
- `set_output(key: str, value: str)`

## Significance
Escalations frequently fail because responders skip policy checkpoints or rely on stale notes. This task pressures agents to synthesize ticket metadata, multi-channel transcripts, and policy requirements before issuing the final escalation code, mirroring real on-call workflows.
