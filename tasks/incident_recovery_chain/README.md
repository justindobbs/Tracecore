# incident_recovery_chain@1

## Overview
Follow a deterministic incident recovery handoff chain and output the final
`RECOVERY_TOKEN` value that confirms the mitigation step.

## Mechanics
- Read `/app/README.md` for the output key.
- Follow the handoff files in order (`status.log`, `handoff_1.txt`, `handoff_2.txt`).
- Submit the final `RECOVERY_TOKEN=<value>` via `set_output`.

## Actions
- `list_dir(path: str)`
- `read_file(path: str)`
- `extract_value(content: str, key: str)`
- `set_output(key: str, value: str)`

## Significance
This task models chained operational recovery steps where agents must track a
sequence of handoffs and avoid skipping required intermediate context.
