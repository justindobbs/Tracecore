# Leaderboard Submission Schema

This document describes the normalized JSON records produced by `agent_bench.leaderboard.ingest_bundle`.

## Submission record

Each ingested bundle produces one file at:

```text
deliverables/leaderboard/submissions/<run_id>.json
```

Top-level fields:

- `submission_id`
  - stable identifier derived from `run_id` and `task_ref`
- `ingested_at`
  - UTC timestamp for ingestion time
- `bundle_dir`
  - absolute path to the source evidence bundle
- `run`
  - normalized run summary from `manifest.json`
- `validator`
  - validator snapshot from `validator.json`
- `provenance`
  - bundle signature and signing metadata
- `verify_report`
  - output from bundle verification

## `run` object

Current normalized fields:

- `run_id`
- `trace_id`
- `agent`
- `task_ref`
- `task_id`
- `version`
- `seed`
- `harness_version`
- `started_at`
- `completed_at`
- `success`
- `termination_reason`
- `failure_type`
- `failure_reason`
- `steps_used`
- `tool_calls_used`
- `trace_entry_count`
- `sandbox`

## `provenance` object

Current normalized fields:

- `signature_algorithm`
- `bundle_signature`
- `signing_public_key_pem`
- `signed_file`

## Index file

The aggregate index lives at:

```text
deliverables/leaderboard/index.json
```

Top-level fields:

- `version`
- `generated_at`
- `submissions`

Each `submissions[]` entry includes:

- `submission_id`
- `run_id`
- `agent`
- `task_ref`
- `success`
- `ingested_at`
- `submission_file`

## Stability notes

The normalized submission schema is intended to be additive-first.

Allowed future changes:

- add new fields to top-level objects
- add leaderboard-specific summary metrics
- add optional reviewer or policy metadata

Avoid unless versioned explicitly:

- renaming existing keys
- changing semantic meaning of `success`, `failure_type`, or provenance fields
- dropping the pointer back to the original bundle directory
