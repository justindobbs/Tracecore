# Maintainer (`tracecore maintain`)

## What this feature is

`tracecore maintain` is a small *project maintainer loop* for TraceCore projects (the legacy `agent-bench` alias still works, but docs now use the canonical name).

It runs a standard “health check” sequence from a chosen working directory:

- Task registry validation (`tracecore tasks validate --registry`)
- The Python test suite (`pytest`)
- Optional guarded fixers applied to specific files you point it at

The command prints a **machine-readable JSON summary** and exits non-zero when something important fails.

### Why it exists

In practice, TraceCore work often involves:

- Evolving agent code
- Evolving task manifests and task runtime contracts
- Evolving runner behavior

When those move, you want a fast way to:

- Detect what broke (tests / registry validation)
- Apply *safe, mechanical* fixes for known sharp edges
- Produce a structured report that CI or a script can consume

This is especially useful while iterating on deterministic execution and record/replay behaviors: it gives you a repeatable “is the project still healthy?” check.

## What this feature is **not**

`agent-bench maintain` is intentionally conservative.

- **Not an AI coding agent**
  - It does not call an LLM.
  - It does not attempt to reason about your project or invent changes.
- **Not a general formatter or linter runner**
  - It does not run `ruff`, `black`, `mypy`, etc. (unless you explicitly pass them via custom scripts outside of this command).
- **Not a refactoring tool**
  - Fixers are narrowly scoped and should be obviously correct.
- **Not a replacement for code review**
  - `--apply` can modify files. You should still review diffs.
- **Not a “make everything pass” button**
  - When tests fail, it reports failure; it does not try arbitrary edits.

## When to use it

- **Before committing**: run `agent-bench maintain` locally to ensure tasks and tests are sane.
- **In CI**: run `agent-bench maintain` so failures yield a single JSON artifact and a single exit code.
- **When onboarding**: it’s a single command that confirms a working environment.
- **When you hit a known sharp edge**: use `--fix-agent ...` to apply a targeted, known-safe rewrite.

## Basic usage

Run from the repository root:

```bash
tracecore maintain
```

### Exit codes

- `0` when `ok: true`
- `1` when `ok: false`

In other words, this command is suitable for CI gating.

## Skipping task registry validation

If you are iterating on tests only (or you know registry validation is noisy for your current change), you can skip it:

```bash
tracecore maintain --no-tasks-validate
```

## Passing arguments through to pytest

You can pass extra pytest flags.

### Recommended form: use `--` passthrough

This is the most reliable pattern:

```bash
tracecore maintain -- --maxfail=1 -q
```

Everything after `--` is forwarded to pytest.

### Alternative form: `--pytest-args`

```bash
tracecore maintain --pytest-args -q
```

Note: `--pytest-args` uses a “consume the rest of the command line” parse mode. That means any maintain flags placed *after* `--pytest-args` may be interpreted as pytest args instead.

Because of that, if you use `--pytest-args`, put it last.

## Applying guarded fixers

Fixers are **opt-in** and run only on the files you explicitly list.

### Dry-run by default

By default, `maintain` will *suggest* changes but will not write them:

```bash
tracecore maintain --fix-agent path/to/some_agent.py
```

The JSON output includes a `fixes` array with entries like:

- `changed: true` and `dry_run: true` when a rewrite is suggested
- `changed: false` when nothing matched

### Applying changes

Use `--apply` to write changes in place:

```bash
tracecore maintain --fix-agent path/to/some_agent.py --apply
```

### Multiple files

Repeat `--fix-agent`:

```bash
tracecore maintain --fix-agent a.py --fix-agent b.py --apply
```

### Failure behavior for fix targets

If you pass a file that doesn’t exist, `maintain` reports an error per file and the overall run fails:

- The `fixes` entry includes `error: "not_found"`
- `fix_errors` is incremented
- `ok` becomes `false`
- Exit code is `1`

This is deliberate: it prevents CI from “passing” when a requested fix never ran.

## Current fixers

### Pydantic AI import aliasing

**Problem**

Some agent examples import Pydantic AI like:

```python
from pydantic_ai import Agent
```

Agent-Bench’s loader prefers a module-level attribute named `Agent`. If `pydantic_ai.Agent` is present under that name at module scope, the loader may load the wrong class and you’ll see runtime errors (for example, missing `reset`).

**Fix**

The fixer rewrites:

```python
from pydantic_ai import Agent, RunContext
```

to:

```python
from pydantic_ai import Agent as PydanticAgent, RunContext
```

This preserves functionality while avoiding name collisions with the TraceCore agent contract.

## Output format

The command prints a single JSON object.

Top-level fields:

- `cwd`: working directory used
- `tasks_validate`: subprocess summary for `agent-bench tasks validate --registry` (if enabled)
- `pytest`: subprocess summary for pytest
- `fixes`: list of fixer results (one per `--fix-agent` file)
- `fix_errors`: count of fixer entries that include an `error`
- `ok`: overall success flag

### Example output (abridged)

```json
{
  "cwd": "...",
  "tasks_validate": {"returncode": 0, "stdout": "...", "stderr": "..."},
  "pytest": {"returncode": 0, "stdout": "...", "stderr": "..."},
  "fixes": [{"path": "...", "changed": true, "dry_run": true}],
  "fix_errors": 0,
  "ok": true
}
```

## Safety and operational notes

- **Treat `--apply` as a write operation**
  - Run it on a clean working tree so diffs are easy to review.
- **Keep fixers deterministic and mechanical**
  - If a fixer cannot be obviously correct, it does not belong in this command.
- **Prefer CI visibility**
  - Because output is structured JSON, you can archive it as a CI artifact.

## Troubleshooting

### “pytest got unrecognized arguments: --fix-agent”

This happens when `--fix-agent` is accidentally forwarded to pytest (typically due to `--pytest-args` consuming the remainder).

Prefer the passthrough form:

```bash
tracecore maintain --fix-agent path/to/file.py -- --maxfail=1 -q
```

### Fix says `changed: true` but file didn’t change

That is expected in dry-run mode. Add `--apply` to write changes.

### Fix shows `changed: false`

Either:

- The file doesn’t match any fixer patterns, or
- It was already fixed (idempotent behavior)
