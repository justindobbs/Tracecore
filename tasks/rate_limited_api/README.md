# rate_limited_api

Retrieve a protected `ACCESS_TOKEN` from a mock HTTP API that enforces a strict rate
limit and emits transient failures. The agent must classify structured errors,
respect `retry_after`, and only submit the final token via `set_output` after it
has been fetched successfully.

## Actions
- `call_api(endpoint: str, payload: dict | str | null)` – Call the `/token`
  endpoint. Returns either `{ok: True, data: {token: ...}}` or `{ok: False,
  error: <code>, retry_after?, message?}`. Valid error codes: `rate_limited`,
  `temporary_failure`, `bad_request`, `not_found`.
- `wait(steps: int)` – Advance the virtual clock to let quotas reset.
- `inspect_status()` – Exposes remaining wait time, call counters, etc.
- `get_client_config()` – Returns the payload template the agent must send.
- `set_output(key: str, value: str)` – Only `ACCESS_TOKEN` is accepted.

## Hints
- Always respect `retry_after` before retrying.
- Transient failures can be retried immediately without waiting.
- Sending the wrong payload increments `bad_request` counters and wastes budget.
- The validator only accepts the exact token returned by the API.
