# Artifact Migration Playbook

Use this playbook when upgrading a repository or CI workflow from older TraceCore / Agent-Bench run artifacts to the current spec-aligned artifact shape.

This is primarily for teams carrying forward historical files under `.agent_bench/runs/` that predate the newer strict-spec metadata fields.

## When you need this

Run migration when one or more of the following is true:

- Historical run artifacts are missing fields such as `spec_version`, `runtime_identity`, `agent_ref`, `budgets`, or `artifact_hash`
- `tracecore verify --strict-spec` fails on older run artifacts
- You are preparing CI or release evidence that relies on the current TraceCore artifact contract
- You upgraded from older `agent-bench` / pre-v1.0 workflows and want run history to remain usable

## What the migration tool does

`tracecore runs migrate` scans `.agent_bench/runs/*.json` and backfills legacy artifacts to the current schema.

Today it normalizes or backfills:

- `spec_version`
- `agent_ref`
- `runtime_identity`
- `budgets`
- `artifact_hash`
- missing `action_trace` structural fields required by strict-spec validation
- failure taxonomy defaults when older artifacts omitted `failure_type`

The migration is intentionally conservative:

- it only touches run artifacts
- it does not alter task source files, bundles, or ledger entries
- dry-run mode is the default so CI can detect drift without rewriting files

## Recommended workflow

### 1. Inspect what would change

Run the migration command in dry-run mode first:

```powershell
tracecore runs migrate
```

Behavior:

- exits `0` if no migration is needed
- exits `1` if one or more artifacts would be rewritten
- prints a JSON report with `changed`, `files`, and `errors`

### 2. Rewrite artifacts in place

If the dry-run report shows changes, apply them:

```powershell
tracecore runs migrate --write
```

This rewrites legacy `.json` files under `.agent_bench/runs/` in place.

### 3. Re-run strict validation

After rewriting, confirm the upgraded artifacts are compatible with the current contract:

```powershell
tracecore verify --latest --strict-spec --json
```

If you want broader confidence, also run the focused migration tests:

```powershell
python -m pytest tests/test_run_migration.py tests/test_cli_runs_migrate.py
```

## CI hook pattern

Use dry-run mode in CI to fail fast when historical artifacts drift from the current schema:

```powershell
tracecore runs migrate
```

Typical policy:

- local/dev: run `tracecore runs migrate --write`
- CI: run `tracecore runs migrate` and fail if changes are required

This keeps committed artifacts current without silently mutating files during CI.

## Custom run directory

If your workflow archives run artifacts outside the default directory, point the tool at that root explicitly:

```powershell
tracecore runs migrate --root artifacts/legacy-runs
tracecore runs migrate --root artifacts/legacy-runs --write
```

## Operational cautions

- migrate before generating new compliance evidence from old run artifacts
- do not assume migrated historical artifacts are equivalent to replay-verified bundles; migration fixes schema shape, not behavioral determinism
- if artifacts are also referenced by external reports, preserve a backup or commit the migration as a dedicated change for auditability

## Suggested release / repo hygiene

When upgrading a long-lived branch or release line:

1. Run `tracecore runs migrate`
2. Apply `tracecore runs migrate --write` if needed
3. Re-run strict validation and focused tests
4. Commit the rewritten artifacts separately from unrelated product changes when possible
5. Note the migration in release or upgrade notes if downstream teams consume stored run artifacts

## Related docs

- [TraceCore CLI commands](../cli/commands.md)
- [Manual verification checklist](manual_verification.md)
- [Debugging playbook](debugging_playbook.md)
