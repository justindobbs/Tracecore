"""Scenario tests for operations tasks."""

from __future__ import annotations

from agent_bench.env.environment import Environment

import tasks.config_drift_remediation.actions as drift_actions
import tasks.config_drift_remediation.setup as drift_setup
import tasks.config_drift_remediation.validate as drift_validate
import tasks.incident_recovery_chain.actions as recovery_actions
import tasks.incident_recovery_chain.setup as recovery_setup
import tasks.incident_recovery_chain.validate as recovery_validate
import tasks.log_alert_triage.actions as triage_actions
import tasks.log_alert_triage.setup as triage_setup
import tasks.log_alert_triage.validate as triage_validate


def _init_env(setup_module, actions_module, seed: int = 101) -> Environment:
    env = Environment()
    setup_module.setup(seed, env)
    actions_module.set_env(env)
    return env


def test_log_alert_triage_flow():
    env = _init_env(triage_setup, triage_actions)

    readme = triage_actions.read_file("/app/README.md")
    assert readme["ok"] is True
    target_key = triage_actions.extract_value(readme["content"], "TARGET_KEY")
    assert target_key["ok"] is True

    incident = triage_actions.read_file("/app/incident.log")
    assert incident["ok"] is True
    extracted = triage_actions.extract_value(incident["content"], target_key["value"])
    assert extracted["ok"] is True

    set_result = triage_actions.set_output(target_key["value"], extracted["value"])
    assert set_result["ok"] is True

    validation = triage_validate.validate(env)
    assert validation["ok"] is True


def test_config_drift_remediation_flow():
    env = _init_env(drift_setup, drift_actions)

    readme = drift_actions.read_file("/app/README.md")
    key = drift_actions.extract_value(readme["content"], "TARGET_KEY")
    assert key["ok"] is True

    desired = drift_actions.read_file("/app/desired.conf")
    assert desired["ok"] is True
    max_conn = drift_actions.extract_value(desired["content"], "MAX_CONN")
    assert max_conn["ok"] is True

    patch = f"MAX_CONN={max_conn['value']}"
    set_result = drift_actions.set_output(key["value"], patch)
    assert set_result["ok"] is True

    validation = drift_validate.validate(env)
    assert validation["ok"] is True


def test_incident_recovery_chain_flow():
    env = _init_env(recovery_setup, recovery_actions)

    readme = recovery_actions.read_file("/app/README.md")
    key = recovery_actions.extract_value(readme["content"], "TARGET_KEY")
    assert key["ok"] is True

    handoff = recovery_actions.read_file("/app/handoff_2.txt")
    assert handoff["ok"] is True
    token = recovery_actions.extract_value(handoff["content"], key["value"])
    assert token["ok"] is True

    set_result = recovery_actions.set_output(key["value"], token["value"])
    assert set_result["ok"] is True

    validation = recovery_validate.validate(env)
    assert validation["ok"] is True
