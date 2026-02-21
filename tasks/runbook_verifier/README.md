# runbook_verifier@1

Validate that every incident runbook phase executed in order and report the
combined checksum using the `RUNBOOK_CHECKSUM` output key.

Artifacts shipped with the task:

- `runbook_index.md` – ordered list of phases and the files that document them.
- `phase.md` – detailed metadata for each phase, including the authoritative
  phase code that must appear in the checksum.
- `sequence.log` – deterministic execution log confirming the status of each
  phase.
- `timeline.log` – linearized incident timeline with the final ACK identifier.
- `handoff.md` – explains how to stitch the phase codes + ACK + handoff token
  into the final checksum string.

Follow the README instructions inside the task sandbox for the exact steps.
