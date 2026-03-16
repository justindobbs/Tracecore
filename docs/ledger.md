# TraceCore Ledger

The TraceCore Ledger is the trust-facing index for certified agents, signed evidence bundles, and registry-level provenance.

This page is the operator entry point for the Ledger workflow. It explains how ledger snapshots relate to run artifacts and bundles, and which CLI verbs to use when you want to inspect, seal, verify, or audit evidence.

For the full registry schema, provenance field reference, and governance details, see:

- `docs/governance/ledger.md`
- `docs/governance/ledger_governance.md`

## What the Ledger is

The Ledger is a static registry stored at:

`agent_bench/ledger/registry.json`

It is not the same thing as a live run log.

- **Run artifacts** live in `.agent_bench/runs/`
- **Baseline bundles** live in `.agent_bench/baselines/`
- **Ledger entries** summarize trusted/certified evidence for known agents
- **Registry signatures** prove the top-level ledger snapshot has not been tampered with

In practice, the Ledger is the human-readable and machine-verifiable index that points at the evidence you produced with the run / verify / bundle workflow.

## Core workflow

A typical evidence flow looks like this:

```bash
tracecore run --agent agents/my_agent.py --task filesystem_hidden_config@1 --seed 0
tracecore verify --latest
tracecore bundle seal --latest
tracecore bundle status
tracecore ledger
tracecore ledger verify --registry
```

That flow gives you:

- a run artifact
- replay / strict verification surfaces
- a sealed bundle directory
- visibility into the current ledger registry and signed evidence state

## CLI verbs

### Inspect ledger entries

```bash
tracecore ledger
tracecore ledger --show toy_agent
tracecore ledger --show agents/toy_agent.py
```

Use this when you want to:

- list known ledger entries
- inspect the recorded tasks for an agent
- confirm which agent path or suite a certified entry belongs to

### Seal evidence bundles

```bash
tracecore bundle seal --latest
tracecore bundle seal --run <RUN_ID>
```

Use bundle seal when you want a durable evidence directory that can be verified or referenced later.

### Inspect bundle status

```bash
tracecore bundle status
tracecore bundle status --latest
```

Use this to confirm whether recent bundles exist and whether they are in a good state for follow-up verification or release evidence.

### Verify ledger and bundle signatures

```bash
tracecore ledger verify --registry
tracecore ledger verify --entry toy_agent
tracecore ledger verify --bundle .agent_bench/baselines/<run_id>
```

These checks answer different questions:

- **`--registry`**
  - has the top-level ledger snapshot been signed correctly?

- **`--entry`**
  - do the signed bundle references for one ledger entry verify correctly?

- **`--bundle`**
  - does one local evidence bundle verify against its signature/provenance?

## Ledger snapshots vs. live metrics

Use the right surface for the right job:

- **`tracecore ledger`**
  - static trusted registry view

- **`tracecore baseline`**
  - computed aggregate metrics from persisted runs

- **`tracecore diff`**
  - pairwise divergence analysis between run artifacts

- **`tracecore verify`**
  - replay / strict validation against a run or bundle

The Ledger is intentionally slower-moving and trust-oriented. Baselines and diffs are better for active debugging and iteration.

## What a ledger snapshot contains

A ledger snapshot can include:

- agent identity
- task coverage
- success-rate style summary metrics
- provenance fields like signing time and public-key identity
- per-task bundle references and signatures

For the exact field definitions, see `docs/governance/ledger.md`.

## Release and trust evidence

During release preparation, the Ledger participates in the trust pipeline by anchoring signed evidence.

Typical release-facing artifacts include:

- signed bundle directories
- registry provenance fields in `agent_bench/ledger/registry.json`
- release-time trust bundles under `deliverables/trust_bundle_vX.Y.Z/`

If you are preparing a release, also follow:

- `docs/operations/release_process.md`
- `docs/governance/ledger.md`
- `docs/governance/ledger_governance.md`

## Related docs

- `docs/governance/ledger.md`
- `docs/governance/ledger_governance.md`
- `docs/operations/release_process.md`
- `docs/operations/artifact_migration_playbook.md`
