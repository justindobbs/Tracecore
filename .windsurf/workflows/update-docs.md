---
description: update docs when behavior changes
---

# Update Documentation Workflow

1. **Identify impacted surfaces**
   - Note exactly which user-facing behaviors changed (CLI flags, task APIs, UI labels, agents, etc.).
   - List the docs/examples that currently describe the behavior (README, docs/*.md, CHANGELOG, sample JSON).

2. **Capture before/after details**
   - Copy the new command syntax, JSON keys, or screenshots from the implementation/tests.
   - Record any deprecations or backwards-compatibility notes that should be called out explicitly.

3. **Update primary docs**
   - Edit the canonical reference first (usually README.md or docs/<topic>.md).
   - Use fenced code blocks for commands/JSON; keep tone concise and actionable.

4. **Propagate to secondary references**
   - Run `grep_search` for outdated strings (old flags, field names) across docs/examples and update them.
   - Refresh sample outputs (e.g., examples/sample_output.json) if data schemas changed.

5. **Mention verification/testing**
   - Add a brief note on how to validate the behavior (e.g., `python -m pytest`, `agent-bench runs list --failure-type timeout`).
   - Update `docs/manual_verification.md` if manual steps change.

6. **Review & cite**
   - Re-read changes for clarity and platform neutrality (Windows/macOS/Linux commands).
   - In PR summaries, cite modified doc files with `@filepath#L-L` references.
