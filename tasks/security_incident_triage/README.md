# security_incident_triage@1

## Overview
Triage a deterministic security incident report bundle to recover the authoritative `BREACH_TOKEN` that must be handed to the CSIRT team. Agents must correlate IDS noise, validated findings, and the final incident summary without skipping intermediate steps.

## Mechanics
- Read `/app/README.md` for the scenario context and required output.
- Inspect structured log files under `/app/logs/` and `/app/findings/`.
- Detect and follow the escalation chain described in `/app/incidents/incident.md`.
- Submit `BREACH_TOKEN=<value>` via `set_output` once the confirmed token is located.

## Actions
- `list_dir(path: str)`
- `read_file(path: str)`
- `extract_value(content: str, key: str)`
- `find_line(path: str, needle: str)`
- `set_output(key: str, value: str)`

## Significance
Security incidents rarely live in a single file—agents must stitch together machine alerts and human notes, discard noisy indicators, and confirm the canonical breach token before triggering expensive mitigations. This task stresses disciplined log review, clue correlation, and precise reporting.
