# Leaderboard Design

## Goal

Provide a trustworthy, replay-linked leaderboard preview for TraceCore runs without weakening the existing deterministic evidence model.

The leaderboard is not a replacement for TraceCore's core positioning as a deterministic episode runtime. It is a presentation and submission layer built on top of signed bundles, validator outcomes, and reproducible run artifacts.

## Non-goals for this slice

- no public hosted service
- no anonymous internet submission endpoint
- no new scoring model beyond existing validator outcomes and recorded metrics
- no alternate trust path separate from bundle verification and signing

## Input contract

The ingestion pipeline accepts a local baseline bundle directory that already passed bundle verification and has been signed.

Required files:

- `manifest.json`
- `validator.json`
- `tool_calls.jsonl`
- `integrity.sha256`
- `signature.json`

The ingestion layer rejects unsigned bundles and bundles that fail verification.

## Pipeline stages

### 1. Verify

Run the existing bundle verification checks:

- integrity file consistency
- sandbox declaration presence
- IO audit shape and allowlist checks

### 2. Normalize

Extract stable leaderboard-facing fields from bundle contents:

- run identity
- agent identity
- task reference
- success / failure outcome
- budget consumption counters
- validator snapshot
- signature provenance

### 3. Persist

Write:

- a normalized submission JSON file per run
- a generated `index.json` containing summary rows for listing and later API responses

## Storage layout

```text
deliverables/leaderboard/
  README.md
  design.md
  schema.md
  index.json
  submissions/
    <run_id>.json
```

## Trust model

The leaderboard preview inherits trust from the existing evidence pipeline:

- run artifact
- verify step
- sealed bundle
- bundle signature
- leaderboard ingestion

This means leaderboard rows remain traceable back to the exact certified evidence directory that produced them.

## Why a normalized submission record exists

The bundle format is optimized for verification and replay.
The leaderboard needs a lighter-weight record optimized for:

- listing
- filtering
- API payloads
- future submission review workflows

The normalized submission record keeps only leaderboard-relevant summary data while preserving pointers back to the original bundle directory and validator evidence.

## Future API / CLI path

This slice intentionally stops at a local ingestion primitive:

- Python API: `agent_bench.leaderboard.ingest_bundle(bundle_dir)`

The next Phase 6 step should wire this into:

- FastAPI endpoints for submission/list/detail flows
- CLI commands for local submission and preview inspection

Both surfaces should call the same ingestion primitive to avoid format drift.

## Acceptance criteria for this slice

- signed, verified bundles can be ingested into a normalized leaderboard store
- unsigned bundles are rejected
- verification failures are rejected
- the generated index is deterministic and replaces duplicate run IDs cleanly
- docs describe the contract well enough for a later API/CLI implementation to reuse it directly
