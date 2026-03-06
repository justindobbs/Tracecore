# TraceCore CLI command reference

TraceCore installs the `tracecore` CLI (with a legacy `agent-bench` alias for compatibility). Every command below maps directly to the `argparse` definitions in [`agent_bench/cli.py`](../../agent_bench/cli.py), so this document stays in lockstep with the runtime.

## Run workflows

| Command | Description | Key flags/subcommands |
| --- | --- | --- |
| `tracecore run` | Run an agent against a task once. | `--agent`, `--task`, `--seed`, `--timeout`, `--strict-spec`, `--record`, `--replay`, `--replay-bundle`, `--strict`, `--from-config` |
| `tracecore run pairing` | Launch a known-good `(agent, task)` pairing. | `--list`, `--all`, `--seed`, `--timeout` |
| `tracecore run batch` | Run multiple episodes in parallel worker processes. | `--batch-file`, `--workers`, `--seed`, `--timeout`, `--strict-spec` |
| `tracecore interactive` | Wizard to pick agent/task/seed before running. | `--no-color`, `--save-session`, `--plugins`, `--dry-run` |

## Verification + artifacts

| Command | Description | Key flags |
| --- | --- | --- |
| `tracecore verify` | Verify latest/specified run and optional bundle. | `--latest`, `--run`, `--bundle`, `--strict`, `--strict-spec`, `--json` |
| `tracecore bundle seal` | Seal a baseline bundle from a run. | `--latest`, `--run`, `--sign`, `--key`, `--format` |
| `tracecore bundle status` | List recent bundles and their integrity. | `--limit`, `--format` |
| `tracecore bundle verify` | Verify bundle integrity. | `path`, `--format` |
| `tracecore bundle sign` | Sign a bundle with Ed25519 key. | `path`, `--key`, `--format` |
| `tracecore baseline` | Compute stats, export, compare runs, or bundle. | `--agent`, `--task`, `--limit`, `--export`, `--compare`, `--format`, `--show-taxonomy`, `--bundle`, `--verify` |
| `tracecore diff` | Diff two run artifacts (taxonomy + budgets). | `run_a`, `run_b`, `--format` (pretty/text/json/otlp) |
| `tracecore export otlp` | Emit a run artifact as OTLP JSON spans. | `run`, `--output` |
| `tracecore inspect` | Summarize a stored run artifact (llm_trace preview). | `--run` |

## Run history + metrics

| Command | Description | Key flags |
| --- | --- | --- |
| `tracecore runs list` | List stored run artifacts (JSON). | `--agent`, `--task`, `--limit`, `--failure-type` |
| `tracecore runs summary` | Pretty table of recent runs. | `--agent`, `--task`, `--limit`, `--failure-type` |
| `tracecore runs metrics` | Aggregate reproducibility/budget metrics. | `--agent`, `--task`, `--limit`, `--format` |
| `tracecore runs mttr` | Mean time to recovery per agent/task/seed. | `--agent`, `--task`, `--limit` |
| `tracecore runs migrate` | Dry-run or rewrite legacy run artifacts to the current schema. | `--root`, `--write` |

## Developer tooling

| Command | Description | Key flags |
| --- | --- | --- |
| `tracecore dashboard` | Launch FastAPI dashboard. | `--host`, `--port`, `--reload` |
| `tracecore tasks validate` | Validate manifests and registry entries. | `--path`, `--registry` |
| `tracecore tasks lint` | Lint task contracts (action_schema, sandbox, etc.). | `--path`, `--format` |
| `tracecore maintain` | Run pytest + task validation + guardrail fixes. | `--cwd`, `--pytest-args …`, `--no-tasks-validate`, `--fix-agent`, `--apply` |
| `tracecore new-agent` | Scaffold a reset/observe/act agent stub. | `name`, `--output-dir`, `--force` |
| `tracecore openclaw` | Scaffold/test a TraceCore adapter for OpenClaw. | `--agent-id`, `--task`, `--seed`, `--timeout`, `--gateway` |
| `tracecore openclaw-export` | Export a certified bundle for an OpenClaw adapter. | `--agent-id`, `--out-dir` |
| `tracecore ledger` | List ledger entries or show details. | `--show` |
| `tracecore ledger verify` | Verify ledger registry or bundle signatures. | `--bundle`, `--entry`, `--registry` |
| `tracecore version` | Print runtime + spec version. | — |

> **Tip:** `tracecore` reads defaults from `agent-bench.toml`, so you can omit `--agent/--task` once the config is populated. The `.agent_bench/session.json` pointer keeps `tracecore run → tracecore verify → tracecore bundle seal` loops copy-paste free.
