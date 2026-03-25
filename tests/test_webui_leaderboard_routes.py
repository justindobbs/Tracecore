from __future__ import annotations

from fastapi.testclient import TestClient

from agent_bench.webui import app as webapp
from agent_bench.webui.app import app


SAMPLE_SUBMISSIONS = [
    {
        "submission_id": "run-123:filesystem_hidden_config@1",
        "run_id": "run-123",
        "agent": "agents/toy_agent.py",
        "task_ref": "filesystem_hidden_config@1",
        "success": True,
        "ingested_at": "2026-03-24T12:00:00+00:00",
        "submission_file": "C:/tmp/submission.json",
    }
]


def test_api_leaderboard_returns_json_list(monkeypatch):
    monkeypatch.setattr(webapp, "list_leaderboard_submissions", lambda: SAMPLE_SUBMISSIONS)
    with TestClient(app) as client:
        resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) == 1
    assert payload[0]["run_id"] == "run-123"


def test_api_leaderboard_submission_returns_detail(monkeypatch):
    monkeypatch.setattr(webapp, "load_leaderboard_submission", lambda run_id: {"run": {"run_id": run_id}})
    with TestClient(app) as client:
        resp = client.get("/api/leaderboard/run-123")
    assert resp.status_code == 200
    assert resp.json()["run"]["run_id"] == "run-123"


def test_api_leaderboard_submission_404(monkeypatch):
    monkeypatch.setattr(webapp, "load_leaderboard_submission", lambda run_id: None)
    with TestClient(app) as client:
        resp = client.get("/api/leaderboard/missing")
    assert resp.status_code == 404
    assert resp.json()["error"] == "leaderboard_submission_not_found"


def test_leaderboard_page_renders_entries(monkeypatch):
    monkeypatch.setattr(webapp, "list_leaderboard_submissions", lambda: SAMPLE_SUBMISSIONS)
    with TestClient(app) as client:
        resp = client.get("/leaderboard")
    assert resp.status_code == 200
    assert "TraceCore Leaderboard Preview" in resp.text
    assert "run-123" in resp.text
    assert "/api/leaderboard/run-123" in resp.text
