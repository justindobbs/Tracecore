# config_drift_remediation@1

## Overview
Identify the config drift between desired and live settings, then output the exact
remediation patch line via `set_output` using the provided `TARGET_KEY`.

## Mechanics
- Read `/app/README.md` for the output key.
- Compare `/app/desired.conf` with `/app/live.conf` to find the mismatched entry.
- Submit the full `KEY=VALUE` line that should replace the live value.

## Actions
- `list_dir(path: str)`
- `read_file(path: str)`
- `extract_value(content: str, key: str)`
- `set_output(key: str, value: str)`

## Significance
This task models deterministic config drift remediation: the agent must detect the
exact setting that diverged and report the corrective patch without touching the filesystem.
