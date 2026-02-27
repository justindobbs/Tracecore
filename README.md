# TraceCore (Agent Bench CLI)
[![Tests](https://github.com/justindobbs/Tracecore/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/justindobbs/Tracecore/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)](https://www.python.org/downloads/)
[![PyPI - Version](https://img.shields.io/pypi/v/tracecore?label=tracecore)](https://pypi.org/project/tracecore/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

![TraceCore hero](banner.png)

TraceCore is a lightweight benchmark for action-oriented agents inspired by the OpenClaw style: planner loops, tool APIs, partial observability, but open to any implementation that satisfies the harness.

TraceCore evaluates whether an agent can operate, not just reason. No LLM judges. No vibes. No giant simulators.

> **Brand note:** TraceCore is the product name; the CLI/package and commands remain `agent-bench` for backward compatibility.

TraceCore’s [technical specification](docs/tracecore_spec.md) is the product spine: it defines how the Deterministic Episode Runtime, task harnesses, agents, artifacts, and release governance interlock. Because the spec is enforced end-to-end—artifact-first evidence, deterministic sandboxes, budgeted loops, and governed schema evolution—TraceCore behaves more like CI infrastructure than a leaderboard, which is uncommon in the agent ecosystem.

Core definition: see [`docs/core.md`](docs/core.md) for the Deterministic Episode Runtime primitive and invariant contracts.

If your agent can survive this benchmark, it can probably survive production.

## Quick links
- [Google Colab Example](https://colab.research.google.com/drive/1TLn-rldhE9YwgQqA1IL5KwVkOxA5Gz78?usp=sharing) — hosted copy ready to run without cloning the repo
- [TraceCore technical specification](docs/tracecore_spec.md)
- [Deterministic Episode Runtime spec (`docs/core.md`)](docs/core.md)
- [Task registry & spec freeze](SPEC_FREEZE.md)
- [Release process & historical notes](docs/release_process.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Manual verification checklist](docs/manual_verification.md)

---

## Install TraceCore

| Use case | Command | Notes |
| --- | --- | --- |
| **Stable CLI (recommended)** | `pip install tracecore` | Adds `agent-bench` to your PATH. |
| **uv users** | `uv pip install tracecore` | Same artifact, faster resolver. |
| **pipx / uv tool** | `pipx install tracecore` or `uv tool install tracecore` | Creates isolated shim in `%USERPROFILE%\.local\bin`. |
| **Development** | `git clone https://github.com/justindobbs/Tracecore && cd Tracecore && python -m venv .venv && .venv\Scripts\activate && pip install -e .[dev]` | Keeps CLI + tasks live-edited. |

Windows-specific install guidance (PATH, ExecutionPolicy, uv tool shims) lives in [docs/troubleshooting.md#windows](docs/troubleshooting.md#windows).

### Quick PATH fixes if `agent-bench` isn't found

**Linux/macOS**
```bash
# Add Python user scripts to PATH (run once or add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"
```

**Windows**
```powershell
# Add Python Scripts to PATH (run once or set via System Properties > Environment Variables)
$env:PATH += ";$env:APPDATA\Python\Python312\Scripts"
```

**Isolated install with pipx (recommended)**
```bash
pip install pipx
pipx install tracecore
pipx ensurepath  # Adds pipx shims to PATH
```

**Fallback: run as module**
```bash
python -m agent_bench.cli --help
```

Alias the CLI if you prefer `tracecore`:

```powershell
Set-Alias tracecore agent-bench      # PowerShell profile
doskey tracecore=agent-bench $*      # cmd
alias tracecore='agent-bench'        # Bash/Zsh
```

---

## Feature highlights

| Capability | Why it matters |
| --- | --- |
| **Deterministic Episode Runtime** | Every task freezes its environment, action schema, budgets, and validator, so a `run_id` is reproducible proof of behavior. See [`docs/core.md`](docs/core.md). |
| **Sandboxed tasks** | Task manifests declare filesystem roots + network hosts, enforced by GuardedEnv and surfaced in IO audits. |
| **Binary scoring + telemetry** | Success/failure is the headline; secondary metrics (steps, tool calls, IO audits, validator payloads) keep regressions obvious. |
| **Minimal stack** | Python-only harness + FastAPI dashboard. No Node build tooling, no external services. Runs in seconds on a laptop. |
| **CLI & Web UI parity** | `agent-bench` commands, dashboard, and APIs all call the same runner, so automation matches what maintainers see. |
| **Extensible registry** | Built-in tasks live beside plugin tasks discovered via the `agent_bench.tasks` entry point group. |

TraceCore evaluates planner loops, not single prompts: tool sequencing, retry logic, state tracking, and boring-but-correct behavior under budgets.

---

## Quick start commands

```bash
# Run a known-good pairing
agent-bench run pairing log_stream_monitor
agent-bench run pairing log_stream_monitor --seed 7

See all available pairings:

```bash
agent-bench run pairing --list
agent-bench run pairing --all --timeout 120

# Run explicit agent + task
agent-bench run --agent agents/toy_agent.py --task filesystem_hidden_config@1 --seed 42

# Launch the interactive wizard
agent-bench interactive --dry-run --save-session

# Launch the dashboard
agent-bench dashboard 
or
agent-bench dashboard --reload

# Summaries & baselines
agent-bench runs summary --task log_stream_monitor@1 --limit 10
agent-bench baseline --agent agents/toy_agent.py --task filesystem_hidden_config@1 --export latest

# Scaffold a new agent
agent-bench new-agent my_agent

# Maintainer helper (pytest + task validation)
agent-bench maintain
```

Need a turnkey example? See [`examples/simple_agent_demo`](examples/simple_agent_demo/README.md) for a self-contained CLI, or [`docs/pydantic_poc.md`](docs/pydantic_poc.md) for the deterministic dice-game walkthrough.

---

## Task suites & signals

Frozen tasks live in [`SPEC_FREEZE.md`](SPEC_FREEZE.md). Current operations-focused suites:

| Task | Suite | Goal | Signals |
| --- | --- | --- | --- |
| `filesystem_hidden_config@1` | Filesystem | Discover the one true config key without wrecking the tree. | Selective exploration, state recall. |
| `rate_limited_api@1` | API | Navigate a deterministic rate limit + transient errors to fetch `ACCESS_TOKEN`. | Retry pacing, error classification. |
| `rate_limited_chain@1` | API pain task | Multi-stage handshake + rate limit. | Sequencing, dependency tracking. |
| `deterministic_rate_service@1` | API | Deterministic payload parsing + rate-limits. | Budget management, payload validation. |
| `log_alert_triage@1` | Operations | Triage noisy logs to recover `ALERT_CODE`. | Signal detection, tool economy. |
| `config_drift_remediation@1` | Operations | Compare desired vs. live config and emit the remediation patch. | Diffing discipline, precise edits. |
| `incident_recovery_chain@1` | Operations | Follow a hand-off chain to recover `RECOVERY_TOKEN`. | Long-horizon reasoning, state carry-over. |
| `log_stream_monitor@1` | Operations | Poll paginated logs, ignore noise, emit `STREAM_CODE`. | Patience, trigger detection. |
| `runbook_verifier@1` | Operations | Verify runbook phase execution order and emit `RUNBOOK_CHECKSUM`. | Ordering discipline, multi-artifact stitching. |
| `sandboxed_code_auditor@1` | Operations | Audit sandbox source + logs to emit `ISSUE_ID\|AUDIT_CODE`. | Scoped reads, multi-source extraction. |

Every task ships with a harness (`setup.py`, `actions.py`, `validate.py`, `task.toml`), published hashes, and budgets. Success is binary; steps/tool calls/IO audits provide color.

---

## Architecture & artifacts

```
Agent script  ──▶  Runner (GuardedEnv, budgets, validator)
                      │
                      ├─► IO audit + action trace (JSON)
                      ├─► Baseline exports (.agent_bench/baselines)
                      └─► FastAPI dashboard + REST APIs
```

- **CLI (`agent-bench`)** — runs agents, validates tasks, exports baselines, maintains the repo.
- **Runner** — enforces budgets, sandbox allowlists, structured failure taxonomy.
- **Artifacts** — `.agent_bench/runs/<run_id>.json` (ground truth) + optional `baseline-<ts>.json` for UI compare views.
- **APIs** — `/api/pairings`, `/api/traces/{run_id}?include_io=true`, `/api/ledger` are typed via Pydantic models.
- **Dashboard** — Jinja templates plus FastAPI endpoints; no Node build. Upload a run_id to replay, compare baselines, or visualize IO audits.

Baseline diffs (`agent-bench baseline --compare run_a run_b`) highlight where traces diverge. For CI workflows, see [`docs/ci_workflow.md`](docs/ci_workflow.md).

---

## Web dashboard snapshot

![TraceCore dashboard UI](assets/dashboard.jpeg)

- Launch runs via forms or quick-pick pairings.
- Drill into traces, budget usage, validator payloads, IO audit summaries.
- Filter baselines and recent runs; download artifacts directly.
- Enable `--reload` only during local dev (uvicorn auto-reload). For long-lived servers, omit the flag.

All dashboard actions have CLI equivalents so you can automate the same flows.

---

## Build or extend TraceCore

### Write agents
- Scaffold via `agent-bench new-agent my_agent` (columnar docstrings, budget guards baked in).
- Interface contract lives in [`docs/agents.md`](docs/agents.md) and [`docs/task_harness.md`](docs/task_harness.md).
- Reference agents: `toy_agent.py`, `rate_limit_agent.py`, `chain_agent.py`, `ops_triage_agent.py`, `cheater_agent.py` (sandbox violation test).

### Add tasks
- Built-in tasks register through `tasks/registry.json`; update it plus [`docs/tasks.md`](docs/tasks.md) and `SPEC_FREEZE.md` when bumping versions.
- Plugin pathway: publish a package exposing `agent_bench.tasks` entry points. Template lives in [`docs/task_plugin_template.md`](docs/task_plugin_template.md).
- Every task must include setup/actions/validator files, budgets in `task.toml`, and pass `agent-bench tasks validate --registry`.

---

## Troubleshooting & maintainer workflows

- **Install/CLI issues** — [`docs/troubleshooting.md`](docs/troubleshooting.md) covers PATH fixes, validator errors, dashboard hiccups.
- **Task validation** — `agent-bench tasks validate --registry` ensures manifests + registry stay in lockstep.
- **Maintainer helper** — `agent-bench maintain` runs pytest + task validation and applies mechanical fixes.
- **Manual verification** — Run through [`docs/manual_verification.md`](docs/manual_verification.md) before freezing specs or publishing changelogs.

Task budgets are defined per `task.toml` and cannot be overridden at runtime—agents must respect the published constraints.

---

## Releases & roadmap

- Version metadata lives in `pyproject.toml` and `agent_bench/webui/app.py` (FastAPI banner).
- Changelog is maintained in [`CHANGELOG.md`](CHANGELOG.md); tags follow `vX.Y.Z`.
- Release checklist: [`docs/release_process.md`](docs/release_process.md) — changelog promotion, behavior verification, SPEC_FREEZE update, trust evidence bundle, tagging, publish.
- Plan/shipping updates are captured in [`docs/project_positioning.md`](docs/project_positioning.md) and issue tracker.

TraceCore is intentionally opinionated and evolving. Expect additive task suites, sandbox refinements, and runner upgrades—documented via CHANGELOG + SPEC_FREEZE.

---

## License & acknowledgments

TraceCore (Agent Bench CLI) is MIT Licensed. If you ship improvements (new tasks, agents, dashboard tweaks) open a PR or publish them as plugins. If you disagree with the assumptions, that’s fine: the benchmark is small enough to fork, but contributions that improve determinism, coverage, or ergonomics are always welcome.

> One-line summary: **Terminal Bench energy, but for agents that actually have to do things.**
