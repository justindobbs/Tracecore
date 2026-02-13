# rate_limited_chain@1

Retrieve an `ACCESS_TOKEN` from a chained API that requires a multi-step handshake and enforces strict rate limits.

## Flow
1. Call `/handshake` via `call_api` to obtain a `handshake_id` and expiration step.
2. Read the README instructions (or `get_handshake_template`) to derive the expected phrase.
3. Call `/handshake_commit` with the `handshake_id` and derived response before it expires.
4. Poll `inspect_status` + `wait` to respect `blocked_until` before calling `/token` with the required payload.
5. After a transient failure, retry immediately; once `token` is returned, store it via `set_output` with key `ACCESS_TOKEN`.

Budgets are intentionally tight (steps/tool_calls) to punish brute-force retries.
