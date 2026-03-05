# Pydantic AI Proof of Concept

This proof of concept exercises TraceCore with a lightweight Pydantic AI agent and a deterministic dice task. It demonstrates both the offline deterministic harness tests and the live gateway-backed flow.

## Components

- **Agent**: `agents/dice_game_agent.py`
  - Deterministic mode (default) seeds `random` to keep runs reproducible.
  - Optional Pydantic AI mode (`use_pydantic_ai=True`) wires the agent to `gateway/gemini:gemini-3-flash-preview`.
- **Task**: `tasks/dice_game@1`
  - Deterministic sandbox enforcing a "roll a 4" contract (`max_rolls=3`).
  - Validator inspects hidden state to guarantee replay fidelity.

## Requirements

- Python 3.12+
- `pip install -e ".[pydantic_poc]"` to install TraceCore plus the Pydantic AI extra (or `pip install -e .` followed by `pip install pydantic-ai>=1.66.0`)
- `PYDANTIC_AI_GATEWAY_API_KEY` when exercising the live gateway tests (Option B)

## Option A — Deterministic-only tests

No external network calls required.

```bash
python -m pytest tests/test_dice_game_agent.py -v
```

This verifies seeded rolling, incremental seeding, and the TraceCore agent interface (reset/observe/act).

## Option B — Pydantic AI gateway tests

Requires `PYDANTIC_AI_GATEWAY_API_KEY` in the environment.

```bash
set PYDANTIC_AI_GATEWAY_API_KEY=sk_live_your_key_here   # Windows PowerShell
python -m pytest tests/test_dice_game_pydantic.py -v
```

- `test_pydantic_ai_with_api` drives `run_standalone()` which calls the gateway.
- `test_agent_with_pydantic_mode` instantiates the agent with `use_pydantic_ai=True`.

## Running the dice game task

Once tests pass, run the agent against the deterministic task:

```bash
agent-bench run --agent agents/dice_game_agent.py --task dice_game@1 --seed 42
```

- Deterministic mode requires no credentials and emits the same action trace per seed.
- For Pydantic AI mode, set `PYDANTIC_AI_GATEWAY_API_KEY` and re-run with `TRACECORE_PYDANTIC=1` (or modify the agent instantiation) if you want the CLI episode to call the gateway.

## Record mode workflows

Pair this PoC with `docs/record_mode.md` to test the sealed execution contract:

1. Record a canonical run:
   ```bash
   agent-bench run --agent agents/dice_game_agent.py --task dice_game@1 --seed 42 --record
   ```
2. Replay locally (`agent-bench run ...` without `--record`).
3. Enforce in CI via `agent-bench test --strict`.

Because the dice task and agent are deterministic, mismatches are obvious and easy to debug, making it an ideal sandbox for validating new runtime features.

## Security considerations

- **API keys**: `PYDANTIC_AI_GATEWAY_API_KEY` should be managed via `.env` or your secret manager; never commit it to Git. If you need to pass it at runtime, prefer shell environment exports over inline flags.
- **Network policy**: Only Option B requires external calls. When running record mode with network access, restrict domains to the gateway host you configured.
- **Baseline integrity**: Treat captured baselines as signed artifacts. Re-record only when intentional and always review the tool call JSONL before committing.
- **Prompt injections**: The deterministic dice task is self-contained, but any real tasks or gateway prompts should sanitize observations before feeding them back into the agent. When testing adapters, assert that tool output schemas reject injected instructions instead of blindly relaying them.
