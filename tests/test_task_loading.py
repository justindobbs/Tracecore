"""Task loader coverage."""

from agent_bench.tasks.loader import load_task


def test_load_filesystem_hidden_config():
    task = load_task("filesystem_hidden_config")
    assert task["id"] == "filesystem_hidden_config"
    assert callable(task["setup"].setup)
    assert callable(task["validate"].validate)


def test_load_rate_limited_api():
    task = load_task("rate_limited_api")
    assert task["id"] == "rate_limited_api"
    assert callable(task["setup"].setup)
    assert callable(task["validate"].validate)


def test_load_log_alert_triage():
    task = load_task("log_alert_triage")
    assert task["id"] == "log_alert_triage"
    assert callable(task["setup"].setup)
    assert callable(task["validate"].validate)


def test_load_config_drift_remediation():
    task = load_task("config_drift_remediation")
    assert task["id"] == "config_drift_remediation"
    assert callable(task["setup"].setup)
    assert callable(task["validate"].validate)


def test_load_incident_recovery_chain():
    task = load_task("incident_recovery_chain")
    assert task["id"] == "incident_recovery_chain"
    assert callable(task["setup"].setup)
    assert callable(task["validate"].validate)
