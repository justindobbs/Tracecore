# rate_limited_chain@1

## Overview
Retrieve an `ACCESS_TOKEN` from a chained API that requires a multi-step handshake
*and* enforces strict rate limits. This task layers instruction following on top
of the rate-limit etiquette introduced in `rate_limited_api`.

## Flow
1. Call `/handshake` via `call_api` to obtain a `handshake_id` and expiration step.
2. Read the README instructions (or `get_handshake_template`) to derive the expected phrase.
3. Call `/handshake_commit` with the `handshake_id` and derived response before it expires.
4. Poll `inspect_status` + `wait` to respect `blocked_until` before calling `/token` with the required payload.
5. After a transient failure, retry immediately; once `token` is returned, store it via `set_output` with key `ACCESS_TOKEN`.

## Mechanics
- Skipping the handshake or sending the wrong phrase produces `invalid_handshake`
  / `handshake_required` errors and forces a restart.
- The service exposes a virtual clock and `blocked_until`; agents must calculate
  `retry_after = blocked_until - now` and wait accordingly.
- Payload templates live in hidden state; incorrect payloads yield `bad_request`
  and consume precious tool_calls.

## Agent guidance
1. Cache the handshake template locally and fill it by replacing `<handshake_id>`.
2. After each API error, classify it: fatal (`bad_request`, `invalid_handshake`) ⇒
   restart; transient (`temporary_failure`) ⇒ immediate retry; rate limiting ⇒ wait.
3. Use `inspect_status` sparingly—each call costs budget.
4. Log `handshake_id`, expiration, and payload locally to avoid repeated reads.

## Significance
This task bridges the gap between simple rate limiting and the new depth task
(`deterministic_rate_service`). It verifies that agents can juggle parallel state
machines (handshake + rate window) without exhausting the intentionally tight
budgets highlighted in `docs/tasks.md`.
