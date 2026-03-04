---
description: Why use pipx or uv tool shims for TraceCore
---

# pipx / uv tool shims for TraceCore

TraceCore ships a standard `tracecore` (and `agent-bench`) console entry point. Installing it via `pipx` or `uv tool` wraps that CLI inside an isolated virtual environment, then exposes a lightweight shim on your PATH. This provides the following benefits:

1. **Isolation by default** – The CLI and its Python dependencies live inside a private virtual environment that is decoupled from your global interpreter and any project‑specific venvs. You never risk version conflicts with other packages.
2. **Global convenience** – Even though TraceCore lives in its own venv, the shim behaves like a globally installed binary. You can run `tracecore ...` from any directory without activating an environment first.
3. **Predictable upgrades & removal** – Updating or uninstalling the CLI is a single command (`pipx upgrade tracecore`, `pipx uninstall tracecore`, or the equivalent `uv tool` commands). The entire shimmed environment is rebuilt or removed cleanly without touching other Python installs.
4. **Safer multi-Python setups** – On systems with multiple Python versions, shims ensure the CLI always launches with the interpreter that created the environment. No more “wrong Scripts folder on PATH” mismatches.

> **Do I still need to activate another venv?** No. The shim already lives in its own virtual environment. Simply install with `pipx`/`uv tool` and run `tracecore` directly. For traditional `pip install tracecore` (or editable `pip install -e .[dev]`) setups, you should still create and activate your own `.venv` before installing so the CLI and dependencies stay scoped to that interpreter.

## Quickstart

```bash
pipx install tracecore
# or, with uv
uv tool install tracecore
```

Both commands place the shim in `%USERPROFILE%\.local\bin` on Windows (or `$HOME/.local/bin` on Linux/macOS). Make sure that directory is on your PATH; `pipx ensurepath` or `uv tool install --python 3.12 tracecore` handle this automatically.

For more background on FastAPI’s virtual-environment recommendations, see <https://fastapi.tiangolo.com/virtual-environments/>.
