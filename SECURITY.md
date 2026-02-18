# Security Policy

## Scope

TraceCore is a local benchmark harness. The core package (`agent_bench/` runner, tasks, CLI, and web UI) runs entirely in-process and makes no outbound network calls.

The optional `pydantic_poc` extra (`pip install -e .[pydantic_poc]`) ships an example agent (`agents/dice_game_agent.py`) that can call external LLM APIs (e.g., Gemini) when explicitly invoked via `run_standalone()` or `use_pydantic_ai=True`. That code path is opt-in and not exercised by the benchmark harness itself.

**In scope:**
- Sandbox escape vulnerabilities (agent code reading hidden task state outside the `GuardedEnv` wrapper)
- Arbitrary code execution via task loading or agent loading
- Path traversal in task or agent file resolution

**Out of scope:**
- The optional FastAPI web UI (`agent-bench dashboard`) — it is a local development tool and should not be exposed to untrusted networks
- Vulnerabilities in third-party dependencies (report those upstream)
- Issues that require physical access to the machine running the harness

## Sandbox model

TraceCore's sandbox is **in-process**, not OS-level. The `GuardedEnv` wrapper intercepts calls to hidden state and raises `SandboxViolation`. It is designed to catch accidental or naive cheating attempts (see `agents/cheater_agent.py` for the reference test), not to provide strong isolation against adversarial agent code.

If you need stronger isolation (e.g., running untrusted third-party agents), run the harness inside a container or VM.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report privately via [GitHub Security Advisories](https://github.com/justindobbs/Tracecore/security/advisories/new) or by emailing the maintainer directly (see the GitHub profile for contact details).

Include:
- A description of the vulnerability and its impact
- Steps to reproduce (a minimal script or agent file is ideal)
- The output of `pip show agent-bench` and `python --version`

We aim to acknowledge reports within 5 business days and resolve confirmed issues before public disclosure.
