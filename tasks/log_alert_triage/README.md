# log_alert_triage@1

## Overview
Triage deterministic service logs and submit the final `ALERT_CODE` that identifies
which incident should be escalated.

## Mechanics
- Read `/app/README.md` to discover the required output key (`TARGET_KEY`).
- Scan the generated log artifacts (`/app/service.log`, `/app/incident.log`).
- Exactly one file contains the final `ALERT_CODE=<value>` line.

## Actions
- `list_dir(path: str)`
- `read_file(path: str)`
- `extract_value(content: str, key: str)`
- `set_output(key: str, value: str)`

## Significance
This task introduces deterministic log-triage behavior where agents must move from
telemetry symptoms to the correct escalation code without free-form judging.
