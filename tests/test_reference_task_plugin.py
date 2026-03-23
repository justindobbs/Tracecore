from __future__ import annotations

import base64
import importlib.util
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agent_bench.ledger.signing import load_private_key, sign_bytes, verify_bytes


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "examples" / "reference_task_plugin"
PLUGIN_TASK_DIR = (
    PLUGIN_ROOT
    / "tracecore_reference_task_plugin"
    / "tasks"
    / "reference_echo_task"
)
PLUGIN_PACKAGE_INIT = PLUGIN_ROOT / "tracecore_reference_task_plugin" / "__init__.py"


def _load_reference_plugin_module():
    spec = importlib.util.spec_from_file_location("tracecore_reference_task_plugin", PLUGIN_PACKAGE_INIT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_task_plugin_registers_descriptor():
    plugin_module = _load_reference_plugin_module()
    descriptors = plugin_module.register()
    assert len(descriptors) == 1
    descriptor = descriptors[0]
    assert descriptor["id"] == "reference_echo_task"
    assert descriptor["version"] == 1
    assert Path(descriptor["path"]).resolve() == PLUGIN_TASK_DIR.resolve()


def test_reference_task_plugin_task_directory_passes_registry_validation():
    from agent_bench.tasks.registry import validate_task_path

    assert validate_task_path(PLUGIN_TASK_DIR) == []


def test_reference_task_plugin_tasks_lint_passes():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_bench.cli",
            "tasks",
            "lint",
            "--path",
            str(PLUGIN_TASK_DIR),
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_reference_task_plugin_tasks_validate_passes():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_bench.cli",
            "tasks",
            "validate",
            "--path",
            str(PLUGIN_TASK_DIR),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_reference_task_plugin_signing_roundtrip():
    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    encoded = base64.b64encode(pem).decode("utf-8")
    loaded = load_private_key(encoded)
    payload = PLUGIN_ROOT.joinpath("pyproject.toml").read_bytes()
    signature = sign_bytes(payload, loaded)
    assert verify_bytes(payload, signature, private_key.public_key())
