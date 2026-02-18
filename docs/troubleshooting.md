# Troubleshooting Guide

A quick reference for the most common TraceCore/`agent-bench` issues across installation,
CLI runs, tasks, and the optional web UI. When in doubt, inspect the latest artifact in `.agent_bench/runs/`.

> Tip: Load `.agent_bench/runs/<run_id>.json` directly, or use `agent-bench runs list --limit 5`
> to find recent run IDs. The dashboard trace viewer at `/?trace_id=<run_id>` surfaces the same
> validator and harness messages.

---

## 1. Installation & Environment

### `agent-bench: command not found`

- Ensure you ran `pip install -e .[dev]` (editable install keeps CLI + registry in sync).
- Activate the virtualenv before running commands (`.venv\Scripts\activate` on Windows).
- Verify you are invoking the same interpreter that owns the editable install (e.g., `which python`).

**Windows-specific**

- Add `%APPDATA%\Python\Python3x\Scripts` (or the `pipx` shim dir) to `PATH`. See the
  "Windows PATH tip" in `README.md` for step-by-step instructions.
- After editing `PATH`, open a new terminal so the shell picks up the change.

**Common pitfalls**

- Launching `agent-bench` from PowerShell after activating the virtualenv in Command Prompt (or
  vice versa). Activate the env in the same shell you use to run the CLI so `PATH` and `PYTHONPATH`
  match.
- Running commands from inside the `.venv/` folder. Always run `agent-bench` from the repo root so
  relative imports (tasks, agents) resolve correctly.

### `ModuleNotFoundError: No module named 'agent_bench'`

The package is not on `PYTHONPATH`. Activate the same virtualenv used for installation or
export `PYTHONPATH="$(pwd)"` temporarily. Reinstall with `pip install -e .` if the editable
link was removed.

### Mixed Python versions between install and runtime

If `python` points at a different interpreter than the one that ran `pip`, the scripts land in
another `site-packages`. Pin a single interpreter via `py -3.12 -m venv .venv && .venv\Scripts\activate`
(Windows) or `python3.12 -m venv .venv` (macOS/Linux).

---

## 2. CLI Invocation Errors

### Quick-start: `run pairing`

The fastest way to fire a known-good run without memorizing flags:

```bash
agent-bench run pairing log_stream_monitor          # run by name, seed 0
agent-bench run pairing log_stream_monitor --seed 7 # custom seed
agent-bench run pairing --list                      # show all available pairings
```

If you are inside a directory that contains exactly one paired agent file, the name can be omitted and it auto-selects. If the name is unknown or ambiguous, the CLI prints the pairing list and exits with a non-zero code.

---

### `pytest got unrecognized arguments: --fix-agent`

`agent-bench maintain` forwards flags after `--`. Use:

```bash
agent-bench maintain --fix-agent path/to/file.py -- --maxfail=1 -q
```

See `docs/maintainer.md` for the full command reference.

### `No compatible agent class found`

- The module must expose a class implementing `reset`, `observe`, and `act`.
- Confirm the file path is importable (relative to repo root or absolute path).
- The loader picks the first class in the module that satisfies the interface; rename or reorder classes if multiple candidates exist.

### `Invalid action` failures on start

Compare your emitted action schema to the task docs (`docs/tasks.md` + per-task README).
Common slips:

- Missing `args` dict
- Wrong action `type`
- Returning `None` instead of a dict

### `Budget exhausted` immediately

- Agents that loop without checking observation-provided budgets can churn through steps before
  making progress. Read the `remaining_steps` / `remaining_tool_calls` fields in observations and
  stop early when low.
- For debugging, add logging around each action to confirm you are not retrying the same failing
  call.

### Determinism drift detected

If a re-run produces different traces:

1. Confirm you re-used the same `--seed`, `agent`, and `task`.
2. Inspect `.agent_bench/runs/<run_id>.json` for `harness_version` mismatches.
3. Ensure external randomness (e.g., `random`, numpy, or model sampling) is seeded from `task_spec`.
4. Avoid wall-clock timestamps inside actions; store logical timers instead.

---

## 3. Runner / Validator Outcomes

### `failure_type: invalid_action`

The harness rejected the agent's output. Inspect the trace entry with `"invalid_action_reason"`
for field-level details.

### `failure_type: logic_failure`

The validator declared `{"ok": false, "terminal": true}` or the run ended without a success
condition. Typical causes:

- Required artifact (API key, patch, token) missing or misformatted.
- Agent skipped a validation step (`validate.py` failed its checks).

Open `.agent_bench/runs/<run_id>.json` directly or load `/?trace_id=<run_id>` in the dashboard to see the validator message.

### `failure_type: budget_exhausted`

- Budgets are set in the task's `task.toml` manifest. To debug, temporarily increase them there and re-run.
- Inspect whether you are stuck in recovery loops (e.g., repeating `read_file` on the same path).

### `failure_type: timeout` or `non_termination`

- Timeouts occur only if you passed `--timeout` or a task enforces one.
- `non_termination` is reserved; if you see it, file a bug with the trace and harness version.

---

## 4. Web UI / Dashboard

### Page loads but runs never start

- Confirm the FastAPI server log shows the incoming request. If not, CORS or proxy filters might
  block POSTs.
- Ensure the backend is running in the same environment that has the agents/tasks installed.
- When using `--reload`, the process restarts on file changes; avoid editing large directories while
  running tests.

> **`--reload` is for local development only.** Do not expose the dashboard with `--reload` on
> shared or networked machines. For stable serving, omit the flag.

### `422 Unprocessable Entity` when submitting the form

- Agent path must be relative to repo root or absolute. Use the dropdown or copy/paste from
  `agents/`.
- Task IDs require the `@version` suffix (e.g., `filesystem_hidden_config@1`).
- Seeds must be integers.

### Dashboard shows stale runs

Runs list is cached per session. Force-refresh with `Ctrl+Shift+R` or call
`agent-bench runs list --limit 5` to verify the artifacts exist. If `.agent_bench/runs/` is empty,
ensure the CLI has write permissions (network shares may block file creation).

---

## 5. Maintenance & CI Helpers

### `agent-bench maintain` says `changed: true` but files are untouched

You are running in dry-run mode. Add `--apply` to write changes.

### `changed: false` but file still violates style

Either the fixer does not target that file, or it is already idempotent. Cross-check the fixer
patterns in `docs/maintainer.md` and run the dedicated formatter (e.g., `ruff format`, `black`)
if needed.

### CI fails with `agent-bench run ... exited 1`

- Re-run locally with the `--seed` reported in CI.
- Check for relative paths that only exist on CI runners (e.g., `/home/runner/work/...`). Use
  repo-relative paths instead.
- If CI lacks the recorded agent dependencies, ensure `pyproject.toml` extras cover them and
  `pip install -e .[dev]` is part of the workflow (see `docs/ci_workflow.md`).

---

## 6. When All Else Fails

1. Inspect the latest `.agent_bench/runs/<run_id>.json` for harness + validator messages.
2. Reproduce with a fixed `--seed` and inspect the resulting artifact.
3. Capture environment details:
   - `python --version`
   - `pip show agent-bench`
   - OS / shell
4. Cross-reference specialized docs:
   - `docs/agent_interface.md` for contract issues
   - `docs/task_manifest.md` + per-task READMEs for action schemas
   - `docs/record_mode.md` and `docs/manual_verification.md` for replay workflows
5. File an issue with the above details if the problem persists.
