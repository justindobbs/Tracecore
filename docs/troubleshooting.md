# Troubleshooting Guide

A quick reference for the most common TraceCore/`agent-bench` issues across installation,
CLI runs, tasks, and the optional web UI. When in doubt, inspect the latest artifact in `.agent_bench/runs/`.

> Tip: Load `.agent_bench/runs/<run_id>.json` directly, or use `agent-bench runs list --limit 5`
> to find recent run IDs. The dashboard trace viewer at `/?trace_id=<run_id>` surfaces the same
> validator and harness messages.

---

## 1. Installation & Environment

### Development vs Pip Install: Which setup do you have?

**Development (git clone) setup:**
```bash
git clone https://github.com/justindobbs/Tracecore.git
cd Tracecore
python -m venv .venv && .venv\Scripts\activate
pip install -e .[dev]
```
- Live edits to CLI/tasks/agents work immediately
- Uses local files directly from repo
- Run from repo root for relative imports

**Pip install setup:**
```bash
pip install tracecore
# or
pipx install tracecore
```
- Installed to system/site-packages
- Must reinstall to get updates
- Works from any directory

### Testing your packaged install (mirrors CI)

```bash
# From repo root - build and test wheel
python -m build --wheel
python -m venv .tmp-tracecore
.tmp-tracecore\Scripts\pip install dist\tracecore-*.whl

# Verify it works
.tmp-tracecore\Scripts\agent-bench --help
.tmp-tracecore\Scripts\agent-bench run pairing --list
```

### `agent-bench: command not found`

- Ensure you ran `pip install -e .[dev]` (development setup) OR `pip install tracecore` (pip setup).
- Activate the virtualenv before running commands (`.venv\Scripts\activate` on Windows).
- Verify you are invoking the same interpreter that owns the install (e.g., `which python`).

**Development setup specific:**
- Run from repo root so relative imports (tasks, agents) resolve correctly.
- Use `pip install -e .[dev]` if the editable link was removed.

**Pip install setup specific:**
- Should work from any directory - no need to be in repo root.
- Reinstall with `pip install --upgrade tracecore` to get updates.

**Windows-specific**

- Add `%APPDATA%\Python\Python3x\Scripts` (or the `pipx` shim dir) to `PATH`. See the
  "Windows PATH tip" in `README.md` for step-by-step instructions.
- After editing `PATH`, open a new terminal so the shell picks up the change.

**Common pitfalls**

- Launching `agent-bench` from PowerShell after activating the virtualenv in Command Prompt (or vice versa). Activate the env in the same shell you use to run the CLI so `PATH` and `PYTHONPATH` match.
- Development setup: Running commands from inside the `.venv/` folder. Always run `agent-bench` from the repo root so relative imports (tasks, agents) resolve correctly.
- Pip setup: Expecting live edits to work. Changes require rebuilding and reinstalling the package.

### `ModuleNotFoundError: No module named 'agent_bench'`

The package is not on `PYTHONPATH`. 

**Development setup:** Activate the same virtualenv used for installation or reinstall with `pip install -e .` if the editable link was removed.

**Pip setup:** Ensure you're using the correct Python environment where tracecore was installed, or reinstall with `pip install tracecore`.

### Mixed Python versions between install and runtime

If `python` points at a different interpreter than the one that ran `pip`, the scripts land in
another `site-packages`. Pin a single interpreter via `py -3.12 -m venv .venv && .venv\Scripts\activate`
(Windows) or `python3.12 -m venv .venv` (macOS/Linux).

---

## 2. CLI Invocation Errors

### Scaffold a new agent: `new-agent`

Generate a stub with the correct `reset` / `observe` / `act` interface:

```bash
agent-bench new-agent my_agent                        # creates agents/my_agent_agent.py
agent-bench new-agent my-agent                        # kebab-case → MyAgentAgent
agent-bench new-agent my_agent --output-dir src/      # write to a different directory
agent-bench new-agent my_agent --force                # overwrite an existing file
```

The generated file is immediately importable and runnable. Replace the `# TODO` block in `act()` with your decision logic, then test it:

```bash
agent-bench run --agent agents/my_agent_agent.py --task filesystem_hidden_config@1 --seed 0
```

If the file already exists and `--force` is not set, the command exits non-zero with a clear error rather than silently overwriting.

### Quick-start: `run pairing`

The fastest way to fire a known-good run without memorizing flags:

```bash
agent-bench run pairing log_stream_monitor          # run by name, seed 0
agent-bench run pairing log_stream_monitor --seed 7 # custom seed
agent-bench run pairing --list                      # show all available pairings
```

If you are inside a directory that contains exactly one paired agent file, the name can be omitted and it auto-selects. If the name is unknown or ambiguous, the CLI prints the pairing list and exits with a non-zero code.

Smoke-test every pairing in sequence (CI-friendly — exits non-zero if any fail):

```bash
agent-bench run pairing --all
agent-bench run pairing --all --seed 7 --timeout 120   # 120 s wall-clock limit per run
```

### Wall-clock timeout: `--timeout`

Prevent a hung agent from blocking CI indefinitely:

```bash
agent-bench run --agent agents/toy_agent.py --task filesystem_hidden_config@1 --seed 0 --timeout 60
agent-bench run pairing log_stream_monitor --timeout 90
```

If the run exceeds the limit the CLI exits immediately with a non-zero code and a clear message. The timeout is enforced via a daemon thread so the process terminates cleanly.

### Inspect recent runs: `runs summary`

Print a compact table of recent runs without opening the dashboard:

```bash
agent-bench runs summary                                  # last 20 runs
agent-bench runs summary --task log_stream_monitor@1      # filter by task
agent-bench runs summary --failure-type budget_exhausted  # filter by outcome
agent-bench runs summary --limit 5                        # fewer rows
```

For raw JSON (e.g., for scripting) use `agent-bench runs list` with the same filters.

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
