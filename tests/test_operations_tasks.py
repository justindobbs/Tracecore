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
import tasks.runbook_verifier.actions as runbook_actions
import tasks.runbook_verifier.setup as runbook_setup
import tasks.runbook_verifier.validate as runbook_validate
from tasks.runbook_verifier.shared import (
    HANDOFF_PATH,
    README_PATH,
    RUNBOOK_INDEX_PATH,
    SEQUENCE_PATH,
    TARGET_KEY,
    TIMELINE_PATH,
)


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


def test_runbook_verifier_flow():
    env = _init_env(runbook_setup, runbook_actions)

    readme = runbook_actions.read_file(README_PATH)
    assert readme["ok"] is True
    target_line = _extract_line(readme["content"], "TARGET_KEY=")
    assert target_line.split("=", 1)[1] == TARGET_KEY

    index = runbook_actions.read_file(RUNBOOK_INDEX_PATH)
    assert index["ok"] is True

    phase_entries: list[tuple[int, str]] = []
    for line in index["content"].splitlines():
        if line.startswith("PHASE_") and "_PATH=" in line:
            left, path = line.split("=", 1)
            idx = int(left.split("_", 2)[1])
            phase_entries.append((idx, path))
    phase_entries.sort()

    codes: list[str] = []
    for _, path in phase_entries:
        phase_file = runbook_actions.read_file(path)
        assert phase_file["ok"] is True
        code_line = _extract_line(phase_file["content"], "PHASE_CODE=")
        codes.append(code_line.split("=", 1)[1])

    timeline = runbook_actions.read_file(TIMELINE_PATH)
    assert timeline["ok"] is True
    ack_id = _extract_line(timeline["content"], "ACK_ID=").split("=", 1)[1]

    handoff = runbook_actions.read_file(HANDOFF_PATH)
    assert handoff["ok"] is True
    token = _extract_line(handoff["content"], "HANDOFF_TOKEN=").split("=", 1)[1]

    sequence = runbook_actions.read_file(SEQUENCE_PATH)
    assert sequence["ok"] is True
    assert "STATUS=complete" in sequence["content"]

    checksum = "+".join(codes + [ack_id, token])
    set_result = runbook_actions.set_output(TARGET_KEY, checksum)
    assert set_result["ok"] is True

    validation = runbook_validate.validate(env)
    assert validation["ok"] is True


def _extract_line(content: str, prefix: str) -> str:
    for line in content.splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"missing prefix {prefix!r} in content")
