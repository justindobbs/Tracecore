# deterministic_rate_service@1

## Overview
Depth task that combines handshake confirmation, required payload templates,
strict rate limits, and deterministic transient hiccups. Agents must orchestrate
the entire flow without exceeding a tight budget of steps/tool_calls.

## Mechanics
- `call_api` endpoints: `/handshake`, `/handshake_commit`, `/token`.
- The service keeps deterministic virtual time. `rate_limited` responses
  include `retry_after`; agents must call `wait` for that duration.
- Every successful run experiences exactly one `temporary_failure` that should be
  retried immediately.
- Payload templates (client_id + nonce) and handshake templates live in hidden
  state; mismatches produce `bad_request` and reset progress.
- Fatal errors increment internal counters that the validator checks to ensure
  the agent respected the protocol.

## Agent guidance
1. Cache the handshake template, replace `<handshake_id>`, and confirm via
   `/handshake_commit` before touching `/token`.
2. Track `blocked_until` vs. current virtual time to schedule `wait` calls and
   avoid redundant polling.
3. On `bad_request` or `invalid_handshake`, reset local state and restart the
   flow—do not keep hammering `/token`.
4. After the guaranteed `temporary_failure`, retry `/token` immediately; only
   once `ok` is `True` should you call `set_output` with `ACCESS_TOKEN`.

## Significance
This is the "depth" scenario referenced in `docs/tasks.md`: it pressure-tests an
agent's ability to blend instruction following, rate-limit etiquette, and
stateful recovery. Success indicates readiness for rate-limited real-world APIs
that require precise sequencing rather than brute force.
