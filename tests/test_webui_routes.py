"""Smoke tests for the FastAPI web UI routes using httpx.AsyncClient / TestClient."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent_bench.webui import app as webapp
from agent_bench.webui.app import app


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FAKE_TASKS = [
    {
        "id": "filesystem_hidden_config",
        "version": 1,
        "ref": "filesystem_hidden_config@1",
        "suite": "fs",
        "description": "Find the hidden config.",
    }
]
FAKE_AGENTS = ["agents/toy_agent.py"]
FAKE_RUN = {
    "run_id": "deadbeef",
    "agent": "agents/toy_agent.py",
    "task_ref": "filesystem_hidden_config@1",
    "seed": 0,
    "failure_type": None,
    "steps_used": 3,
    "tool_calls_used": 2,
    "action_trace": [
        {
            "step": 1,
            "action": {"type": "noop"},
            "io_audit": [
                {"type": "fs", "op": "read", "path": "/tmp/config"},
                {"type": "net", "op": "connect", "host": "api.local"},
            ],
        }
    ],
}


@pytest.fixture()
def client(monkeypatch):
    """TestClient with all I/O helpers patched to avoid touching the filesystem."""
    monkeypatch.setattr(webapp, "get_task_options", lambda: FAKE_TASKS)
    monkeypatch.setattr(webapp, "get_agent_options", lambda: FAKE_AGENTS)
    monkeypatch.setattr(webapp, "list_runs", lambda **_: [])
    monkeypatch.setattr(webapp, "build_baselines", lambda **_: [])
    monkeypatch.setattr(webapp, "load_latest_baseline", lambda: None)
    monkeypatch.setattr(webapp, "list_pairings", lambda: [])
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "TraceCore" in resp.text


def test_index_contains_task_and_agent(client):
    resp = client.get("/")
    assert "filesystem_hidden_config@1" in resp.text
    assert "toy_agent.py" in resp.text


def test_index_with_unknown_trace_id_shows_error(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run", lambda _: (_ for _ in ()).throw(FileNotFoundError()))
    resp = client.get("/?trace_id=nonexistent")
    assert resp.status_code == 200
    assert "not found" in resp.text.lower()


# ---------------------------------------------------------------------------
# GET /run
# ---------------------------------------------------------------------------

def test_get_run_redirects_to_root(client):
    resp = client.get("/run")
    assert resp.history, "Expected redirect history"
    first = resp.history[0]
    assert first.status_code == 307
    assert first.headers.get("location") == "/"


# ---------------------------------------------------------------------------
# GET /guide
# ---------------------------------------------------------------------------

def test_guide_returns_200(client):
    resp = client.get("/guide")
    assert resp.status_code == 200
    assert "TraceCore Guide" in resp.text


def test_guide_lists_agents(client):
    resp = client.get("/guide")
    assert resp.status_code == 200
    assert "toy_agent" in resp.text or "Agent" in resp.text


# ---------------------------------------------------------------------------
# GET /api/pairings
# ---------------------------------------------------------------------------

def test_api_pairings_returns_json_list(client):
    resp = client.get("/api/pairings")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_api_pairings_shape(monkeypatch):
    from agent_bench.pairings import KnownPairing

    fake_pairing = KnownPairing(
        name="test_pairing",
        agent="agents/toy_agent.py",
        task="filesystem_hidden_config@1",
        description="Test",
    )
    monkeypatch.setattr(webapp, "get_task_options", lambda: FAKE_TASKS)
    monkeypatch.setattr(webapp, "get_agent_options", lambda: FAKE_AGENTS)
    monkeypatch.setattr(webapp, "list_runs", lambda **_: [])
    monkeypatch.setattr(webapp, "build_baselines", lambda **_: [])
    monkeypatch.setattr(webapp, "load_latest_baseline", lambda: None)
    monkeypatch.setattr(webapp, "list_pairings", lambda: [fake_pairing])

    with TestClient(app) as c:
        resp = c.get("/api/pairings")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    entry = data[0]
    assert entry["name"] == "test_pairing"
    assert entry["agent"] == "agents/toy_agent.py"
    assert entry["task"] == "filesystem_hidden_config@1"
    assert "last_run_id" in entry
    assert "last_success" in entry


# ---------------------------------------------------------------------------
# GET /api/traces/{run_id}
# ---------------------------------------------------------------------------

def test_api_trace_returns_run_json(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run", lambda run_id: FAKE_RUN)
    resp = client.get("/api/traces/deadbeef")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "deadbeef"


def test_api_trace_404_for_missing_run(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run", lambda _: (_ for _ in ()).throw(FileNotFoundError()))
    resp = client.get("/api/traces/missing")
    assert resp.status_code == 404
    assert "error" in resp.json()


# ---------------------------------------------------------------------------
# GET /traces/{run_id}  (HTML trace viewer)
# ---------------------------------------------------------------------------

def test_trace_viewer_returns_200_with_valid_run(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run", lambda run_id: FAKE_RUN)
    resp = client.get("/traces/deadbeef")
    assert resp.status_code == 200
    assert "deadbeef" in resp.text
    assert "IO audit" in resp.text


def test_trace_viewer_shows_error_for_missing_run(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run", lambda _: (_ for _ in ()).throw(FileNotFoundError()))
    resp = client.get("/traces/missing")
    assert resp.status_code == 200
    assert "not found" in resp.text.lower()


# ---------------------------------------------------------------------------
# GET /baselines/latest
# ---------------------------------------------------------------------------

def test_baselines_latest_404_when_none(client):
    resp = client.get("/baselines/latest")
    assert resp.status_code == 404


def test_baselines_latest_404_when_file_missing(client, monkeypatch):
    monkeypatch.setattr(
        webapp,
        "load_latest_baseline",
        lambda: {"_path": "/nonexistent/path.json", "_filename": "baseline.json"},
    )
    resp = client.get("/baselines/latest")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/ledger
# ---------------------------------------------------------------------------

def test_api_ledger_returns_json_list(client):
    resp = client.get("/api/ledger")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_api_ledger_entry_shape(client):
    resp = client.get("/api/ledger")
    assert resp.status_code == 200
    entry = resp.json()[0]
    assert "agent" in entry
    assert "suite" in entry
    assert "tasks" in entry
    assert isinstance(entry["tasks"], list)


# ---------------------------------------------------------------------------
# GET /ledger
# ---------------------------------------------------------------------------

def test_ledger_page_returns_200(client):
    resp = client.get("/ledger")
    assert resp.status_code == 200
    assert "TraceCore Ledger" in resp.text


def test_ledger_page_lists_agents(client):
    resp = client.get("/ledger")
    assert resp.status_code == 200
    assert "toy_agent" in resp.text


def test_ledger_page_shows_api_hint(client):
    resp = client.get("/ledger")
    assert resp.status_code == 200
    assert "/api/ledger" in resp.text


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/io-audit
# ---------------------------------------------------------------------------

def test_io_audit_returns_steps_and_summary(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run", lambda run_id: FAKE_RUN)
    resp = client.get("/api/runs/deadbeef/io-audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "deadbeef"
    assert data["task_ref"] == "filesystem_hidden_config@1"
    assert len(data["steps"]) == 1
    step = data["steps"][0]
    assert step["step"] == 1
    assert step["action"] == "noop"
    assert len(step["io_audit"]) == 2


def test_io_audit_summary_counts(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run", lambda run_id: FAKE_RUN)
    resp = client.get("/api/runs/deadbeef/io-audit")
    assert resp.status_code == 200
    summary = resp.json()["summary"]
    assert summary["total"] == 2
    assert summary["filesystem"] == 1
    assert summary["network"] == 1


def test_io_audit_404_for_missing_run(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run", lambda _: None)
    resp = client.get("/api/runs/missing/io-audit")
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_io_audit_empty_trace(client, monkeypatch):
    run_no_trace = {**FAKE_RUN, "action_trace": []}
    monkeypatch.setattr(webapp, "load_run", lambda _: run_no_trace)
    resp = client.get("/api/runs/deadbeef/io-audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["steps"] == []
    assert data["summary"]["total"] == 0


def test_io_audit_step_with_no_io(client, monkeypatch):
    run_no_io = {
        **FAKE_RUN,
        "action_trace": [{"step": 1, "action": {"type": "noop"}, "io_audit": []}],
    }
    monkeypatch.setattr(webapp, "load_run", lambda _: run_no_io)
    resp = client.get("/api/runs/deadbeef/io-audit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["steps"][0]["io_audit"] == []
    assert data["summary"]["total"] == 0


# ---------------------------------------------------------------------------
# GET /api/runs/diff
# ---------------------------------------------------------------------------

FAKE_RUN_B = {
    "run_id": "cafef00d",
    "agent": "agents/toy_agent.py",
    "task_ref": "filesystem_hidden_config@1",
    "seed": 0,
    "failure_type": None,
    "steps_used": 3,
    "tool_calls_used": 2,
    "action_trace": [
        {
            "step": 1,
            "action": {"type": "noop"},
            "io_audit": [
                {"type": "fs", "op": "write", "path": "/tmp/output"},
            ],
        }
    ],
}


def _fake_load_artifact(run_id):
    if run_id == "deadbeef":
        return FAKE_RUN
    if run_id == "cafef00d":
        return FAKE_RUN_B
    raise FileNotFoundError(f"Run {run_id!r} not found")


def test_runs_diff_returns_structured_result(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run_artifact", _fake_load_artifact)
    resp = client.get("/api/runs/diff?a=deadbeef&b=cafef00d")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "step_diffs" in data


def test_runs_diff_summary_fields(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run_artifact", _fake_load_artifact)
    resp = client.get("/api/runs/diff?a=deadbeef&b=cafef00d")
    assert resp.status_code == 200
    s = resp.json()["summary"]
    assert "same_agent" in s
    assert "same_task" in s
    assert "same_success" in s
    assert "io_audit" in s
    assert "added" in s["io_audit"]
    assert "removed" in s["io_audit"]


def test_runs_diff_io_audit_delta(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run_artifact", _fake_load_artifact)
    resp = client.get("/api/runs/diff?a=deadbeef&b=cafef00d")
    assert resp.status_code == 200
    data = resp.json()
    summary_io = data["summary"]["io_audit"]
    assert summary_io["added"] + summary_io["removed"] > 0


def test_runs_diff_404_for_missing_run_a(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run_artifact", _fake_load_artifact)
    resp = client.get("/api/runs/diff?a=missing&b=cafef00d")
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_runs_diff_404_for_missing_run_b(client, monkeypatch):
    monkeypatch.setattr(webapp, "load_run_artifact", _fake_load_artifact)
    resp = client.get("/api/runs/diff?a=deadbeef&b=missing")
    assert resp.status_code == 404
    assert "error" in resp.json()
