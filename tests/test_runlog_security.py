from __future__ import annotations

import pytest

from agent_bench.runner import runlog


def test_run_path_rejects_path_separators():
    with pytest.raises(ValueError):
        runlog.load_run("../evil")
    with pytest.raises(ValueError):
        runlog.load_run("..\\evil")
    with pytest.raises(ValueError):
        runlog.load_run("/abs")
    with pytest.raises(ValueError):
        runlog.load_run(".hidden")


def test_run_path_rejects_bad_chars():
    with pytest.raises(ValueError):
        runlog.load_run("bad*id")
    with pytest.raises(ValueError):
        runlog.persist_run({"run_id": "bad?id"})


def test_run_path_accepts_safe_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(runlog, "RUN_LOG_ROOT", tmp_path)
    runlog.persist_run({"run_id": "abc-123"})
    data = runlog.load_run("abc-123")
    assert data["run_id"] == "abc-123"
