# Leaderboard Deliverable

This directory captures the initial leaderboard design and the repo-local ingestion pipeline contract for TraceCore signed evidence.

## Contents

- `design.md`
  - leaderboard goals, scope, trust model, and rollout plan
- `schema.md`
  - normalized submission record and index contract produced by the ingestion pipeline
- `submissions/`
  - generated normalized submission records created by `agent_bench.leaderboard.ingest_bundle`
- `index.json`
  - generated summary index of ingested submissions

## Current implementation slice

The current ingestion pipeline is intentionally local and file-backed.

Input:

- a verified baseline bundle directory
- a bundle signature file (`signature.json`)
- the existing bundle manifest and validator snapshot

Output:

- one normalized submission file per ingested run
- one aggregate index file under `deliverables/leaderboard/index.json`

## Why this exists before API/CLI submission commands

Phase 6 separates the work into two steps:

1. define and test the canonical leaderboard submission contract
2. expose that contract through FastAPI endpoints and CLI commands

This deliverable completes step 1. The future API/CLI work should call the same ingestion primitive rather than inventing a second submission format.
