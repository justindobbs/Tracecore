# log_stream_monitor@1

**Suite:** operations  
**Version:** 1  
**Deterministic:** yes

## Scenario

A service emits a rolling log stream via a paginated poll endpoint. The stream contains noise entries (INFO, WARN, transient ERROR) across multiple pages. Exactly one page contains a `CRITICAL` entry embedding a `STREAM_CODE` value.

The agent must poll the stream page by page, ignore noise, detect the `CRITICAL` entry, extract the `STREAM_CODE`, and submit it via `set_output`. The agent must stop as soon as it finds the target — the budget is tight enough that exhaustive polling without early exit will fail.

## Action surface

| Action | Args | Returns |
|--------|------|---------|
| `poll_stream` | `cursor: int` | `{"ok": true, "entries": [...], "next_cursor": int, "exhausted": bool}` |
| `set_output` | `key: str, value: str` | `{"ok": true}` |

## Success condition

`agent_output["STREAM_CODE"]` must exactly match the seeded `STREAM_CODE` embedded in the CRITICAL log entry.

## Record mode relevance

`poll_stream` is the action that would be an external HTTP GET in a real deployment. In record mode, each cursor's response would be frozen on first capture and replayed deterministically thereafter — making this task an ideal record mode prototype target.

## Budgets

- Steps: 80  
- Tool calls: 30
