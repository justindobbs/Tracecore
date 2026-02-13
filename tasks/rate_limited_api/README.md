# rate_limited_api

## Overview
Retrieve a protected `ACCESS_TOKEN` from a mock HTTP API that enforces a strict
rate limit and emits transient failures. Agents must classify structured errors,
respect `retry_after`, and only submit the final token via `set_output` after it
has been fetched successfully.

## Mechanics
- Endpoints exposed through `call_api`: `/token` (primary) plus health/error responses.
- The service maintains a virtual clock; exceeding quotas produces `rate_limited`
  along with `retry_after` steps the agent must wait using `wait`.
- Each scenario guarantees at least one `temporary_failure` that should be retried
  immediately without waiting.
- Payload templates are provided via `get_client_config`; deviating produces
  `bad_request` errors and wastes budget.

## Actions
- `call_api(endpoint: str, payload: dict | str | null)` – Call the `/token`
  endpoint. Returns either `{ok: True, data: {token: ...}}` or `{ok: False,
  error: <code>, retry_after?, message?}`. Valid error codes: `rate_limited`,
  `temporary_failure`, `bad_request`, `not_found`.
- `wait(steps: int)` – Advance the virtual clock to let quotas reset.
- `inspect_status()` – Exposes remaining wait time, call counters, etc.
- `get_client_config()` – Returns the payload template the agent must send.
- `set_output(key: str, value: str)` – Only `ACCESS_TOKEN` is accepted.

## Agent guidance
1. Treat `rate_limited` as hard backoff: capture `retry_after` and call `wait` before
   touching `/token` again.
2. Retry `temporary_failure` immediately; no waiting is required.
3. Cache the payload template locally to avoid repeated `get_client_config` calls.
4. Once the token arrives, persist it via `set_output` to exit early.

## Significance
This is the entry-level API scenario described in `docs/tasks.md`. It isolates
rate-limit etiquette and transient-retry discipline before agents graduate to
handshake flows (`rate_limited_chain`) or depth scenarios
(`deterministic_rate_service`).
