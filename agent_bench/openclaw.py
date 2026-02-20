"""OpenClaw agent detection, adapter scaffolding, and export utilities."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

_OPENCLAW_CONFIG_CANDIDATES = [
    Path("openclaw.json"),
    Path.home() / ".openclaw" / "openclaw.json",
]


def detect_openclaw_agent(cwd: Path, agent_id: str | None) -> dict | None:
    """Locate an OpenClaw agent definition from *cwd* or the default config path.

    Supports both config formats:

    - **Canonical** (official docs): ``agents.list`` — array of objects with
      ``id``, ``workspace``, ``agentDir``, ``model``. Prompt content is read
      from ``AGENTS.md`` inside the agent's resolved workspace directory.
    - **Runbook** (community shorthand): ``agents.named`` — object keyed by
      agent ID with ``model`` and optional ``systemPromptFile``.

    Returns a metadata dict::

        {
            "id": "researcher",
            "model": {"primary": "...", "fallbacks": [...]},
            "workspace": Path(...) | None,  # resolved workspace dir
            "prompt_file": Path(...) | None, # AGENTS.md or systemPromptFile
            "prompt_text": "...",
            "config_path": Path(...),
        }

    Returns ``None`` if no config or matching agent is found.
    """
    config_path = _find_config(cwd)
    if config_path is None:
        return None

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    agents_block = config.get("agents", {})
    defaults = agents_block.get("defaults", {})

    # --- canonical format: agents.list (official OpenClaw docs) ---
    agents_list = agents_block.get("list", [])
    if agents_list:
        return _detect_from_list(agents_list, defaults, agent_id, config_path)

    # --- community runbook format: agents.named ---
    named = agents_block.get("named", {})
    if named:
        return _detect_from_named(named, defaults, agent_id, config_path)

    return None


def _detect_from_list(
    agents_list: list,
    defaults: dict,
    agent_id: str | None,
    config_path: Path,
) -> dict | None:
    """Resolve an agent from the canonical agents.list format."""
    if agent_id is None:
        if len(agents_list) == 1:
            agent_cfg = agents_list[0]
        else:
            # Use the one marked default=true, or the first entry
            defaults_marked = [a for a in agents_list if a.get("default")]
            agent_cfg = defaults_marked[0] if defaults_marked else None
            if agent_cfg is None:
                return None
    else:
        agent_cfg = next((a for a in agents_list if a.get("id") == agent_id), None)
        if agent_cfg is None:
            return None

    resolved_id: str = agent_cfg.get("id", "main")
    model = _resolve_model(agent_cfg, defaults)

    # Workspace: per-agent override or defaults.workspace
    workspace_raw = (
        agent_cfg.get("workspace")
        or agent_cfg.get("agentDir")
        or (defaults.get("workspace"))
        or str(Path.home() / ".openclaw" / "workspace")
    )
    workspace_path = Path(workspace_raw).expanduser()
    if not workspace_path.is_absolute():
        workspace_path = config_path.parent / workspace_path
    workspace = workspace_path.resolve()

    # Prompt: AGENTS.md in workspace (canonical bootstrap file)
    prompt_file, prompt_text = _read_bootstrap_prompt(workspace)

    return {
        "id": resolved_id,
        "model": model,
        "workspace": workspace,
        "prompt_file": prompt_file,
        "prompt_text": prompt_text,
        "config_path": config_path,
    }


def _detect_from_named(
    named: dict,
    defaults: dict,
    agent_id: str | None,
    config_path: Path,
) -> dict | None:
    """Resolve an agent from the community runbook agents.named format."""
    if agent_id is None:
        if len(named) == 1:
            agent_id = next(iter(named))
        else:
            return None

    agent_cfg = named.get(agent_id)
    if agent_cfg is None:
        return None

    model = _resolve_model(agent_cfg, defaults)

    # Prompt: systemPromptFile (runbook convention)
    prompt_file_rel = agent_cfg.get("systemPromptFile")
    prompt_file: Path | None = None
    prompt_text = ""

    if prompt_file_rel:
        candidates = [
            config_path.parent / prompt_file_rel,
            Path.home() / ".openclaw" / prompt_file_rel,
        ]
        for candidate in candidates:
            if candidate.exists():
                prompt_file = candidate.resolve()
                try:
                    prompt_text = prompt_file.read_text(encoding="utf-8")
                except OSError:
                    prompt_text = ""
                break

    return {
        "id": agent_id,
        "model": model,
        "workspace": None,
        "prompt_file": prompt_file,
        "prompt_text": prompt_text,
        "config_path": config_path,
    }


def _resolve_model(agent_cfg: dict, defaults: dict) -> dict:
    """Return a normalised {primary, fallbacks} model dict."""
    raw = agent_cfg.get("model") or defaults.get("model") or {}
    if isinstance(raw, str):
        return {"primary": raw, "fallbacks": []}
    return raw


def _read_bootstrap_prompt(workspace: Path) -> tuple[Path | None, str]:
    """Read AGENTS.md from the workspace directory (canonical prompt source)."""
    agents_md = workspace / "AGENTS.md"
    if agents_md.exists():
        try:
            return agents_md.resolve(), agents_md.read_text(encoding="utf-8")
        except OSError:
            pass
    return None, ""


def _find_config(cwd: Path) -> Path | None:
    local = cwd / "openclaw.json"
    if local.exists():
        return local
    for candidate in _OPENCLAW_CONFIG_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Scaffold — self-contained adapter (default)
# ---------------------------------------------------------------------------

def scaffold_openclaw_adapter(agent_meta: dict, out_dir: Path) -> Path:
    """Write a self-contained TraceCore adapter for the given OpenClaw agent.

    The adapter uses the rule-based stub pattern (no live gateway required).
    The user fills in ``act()`` with their decision logic.
    """
    agent_id: str = agent_meta["id"]
    class_name = _to_class_name(agent_id) + "AdapterAgent"
    file_name = agent_id + "_adapter_agent.py"
    target = out_dir / file_name

    prompt_snippet = ""
    if agent_meta.get("prompt_text"):
        first_line = agent_meta["prompt_text"].strip().splitlines()[0][:120]
        prompt_snippet = f"\n# Prompt (first line): {first_line}"

    model_primary = (agent_meta.get("model") or {}).get("primary", "")
    model_note = f"  # OpenClaw model: {model_primary}" if model_primary else ""

    stub = f'''"""TraceCore adapter for OpenClaw agent \'{agent_id}\'.

Auto-generated by `agent-bench openclaw`. This adapter is self-contained:
no live OpenClaw gateway is required. Fill in the act() method with your
decision logic, then test with:

    agent-bench run --agent {file_name} --task <task_ref> --seed 0

To use the live OpenClaw gateway instead, re-scaffold with --gateway.
"""{prompt_snippet}

from __future__ import annotations

AGENT_ID = {agent_id!r}{model_note}


class {class_name}:
    """Self-contained TraceCore adapter for OpenClaw agent \'{agent_id}\'.

    Replace the TODO block in act() with logic that maps the TraceCore
    observation to a task action dict.
    """

    def reset(self, task_spec: dict) -> None:
        """Called once before each episode."""
        self.task_spec = task_spec or {{}}
        self.obs: dict | None = None
        self.step = 0

    def observe(self, observation: dict) -> None:
        """Receive the latest environment observation."""
        self.obs = observation

    def act(self) -> dict:
        """Return the next action dict.

        Action schema::

            {{"type": "<action_type>", "args": {{...}}}}

        Use {{"type": "set_output", "args": {{"key": ..., "value": ...}}}} to
        submit the final answer and end the episode successfully.
        """
        self.step += 1

        if self.obs is None:
            return {{"type": "wait", "args": {{}}}}

        remaining_steps = self.obs.get("remaining_steps", 0)
        remaining_tool_calls = self.obs.get("remaining_tool_calls", 0)

        if remaining_steps <= 1 or remaining_tool_calls <= 1:
            return {{"type": "wait", "args": {{}}}}

        # TODO: implement your OpenClaw agent logic here.
        # Use self.obs["visible_state"] and self.obs["last_action_result"]
        # to decide the next action. See the task README for allowed types.
        return {{"type": "wait", "args": {{}}}}
'''

    out_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(stub, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Scaffold — gateway-wired adapter (--gateway)
# ---------------------------------------------------------------------------

def scaffold_gateway_adapter(agent_meta: dict, out_dir: Path) -> Path:
    """Write a gateway-wired TraceCore adapter for the given OpenClaw agent.

    Requires a running OpenClaw gateway. Each act() call dispatches to the
    gateway via agent / agent.wait RPC and translates the result.
    """
    agent_id: str = agent_meta["id"]
    class_name = _to_class_name(agent_id) + "GatewayAdapterAgent"
    file_name = agent_id + "_gateway_adapter_agent.py"
    target = out_dir / file_name

    model_primary = (agent_meta.get("model") or {}).get("primary", "")
    model_note = f"  # OpenClaw model: {model_primary}" if model_primary else ""

    stub = f'''"""TraceCore gateway adapter for OpenClaw agent \'{agent_id}\'.

Auto-generated by `agent-bench openclaw --gateway`. Requires a running
OpenClaw gateway. Pass a gateway client at construction time:

    from my_openclaw_sdk import OpenClawClient
    agent = {class_name}(client=OpenClawClient())
    agent-bench run --agent {file_name} --task <task_ref> --seed 0

agent.wait default timeout is 30 s; increase via OPENCLAW_WAIT_TIMEOUT_MS env var.
"""

from __future__ import annotations
import os

AGENT_ID = {agent_id!r}{model_note}
_WAIT_TIMEOUT_MS = int(os.environ.get("OPENCLAW_WAIT_TIMEOUT_MS", "25000"))


class {class_name}:
    """Gateway-wired TraceCore adapter for OpenClaw agent \'{agent_id}\'.

    The gateway client must implement:
        client.agent(agent_id, prompt) -> {{"runId": str}}
        client.agent_wait(run_id, timeout_ms) -> {{"status": "ok"|"error"|"timeout", "action": dict}}
    """

    def __init__(self, client=None) -> None:
        self._client = client
        self.obs: dict | None = None
        self.task_spec: dict = {{}}

    def reset(self, task_spec: dict) -> None:
        self.task_spec = task_spec or {{}}
        self.obs = None

    def observe(self, observation: dict) -> None:
        self.obs = observation

    def act(self) -> dict:
        if self.obs is None:
            return {{"type": "wait", "args": {{}}}}

        remaining_steps = self.obs.get("remaining_steps", 0)
        remaining_tool_calls = self.obs.get("remaining_tool_calls", 0)

        if remaining_steps <= 1 or remaining_tool_calls <= 1:
            return {{"type": "wait", "args": {{}}}}

        if self._client is None:
            raise RuntimeError(
                f"No gateway client provided. Pass client= to {{type(self).__name__}}()."
            )

        run = self._client.agent(AGENT_ID, prompt=str(self.obs))
        result = self._client.agent_wait(run["runId"], timeout_ms=_WAIT_TIMEOUT_MS)

        if result.get("status") != "ok":
            return {{"type": "wait", "args": {{}}}}

        # TODO: translate the agent_end payload into a TraceCore action dict.
        # Your plugin\'s agent_end hook should populate result["action"].
        return result.get("action") or {{"type": "wait", "args": {{}}}}
'''

    out_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(stub, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_openclaw_agent(
    agent_meta: dict,
    adapter_path: Path,
    last_run: dict,
    out_dir: Path,
    gateway_adapter_path: Path | None = None,
) -> Path:
    """Write a certified TraceCore export bundle for the given OpenClaw agent.

    Bundle layout::

        <out_dir>/<agent_id>/
            adapter_agent.py          self-contained adapter (tested)
            gateway_adapter_agent.py  gateway-wired adapter (if available)
            openclaw_agent.md         original prompt file (if found)
            manifest.json             certification metadata
            README.md                 usage instructions

    Returns the bundle directory path.
    """
    import importlib.metadata as _meta

    try:
        harness_version = _meta.version("agent-bench")
    except _meta.PackageNotFoundError:
        harness_version = "0.0.0-dev"

    agent_id: str = agent_meta["id"]
    bundle_dir = out_dir / agent_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    adapter_dest = bundle_dir / f"{agent_id}_adapter_agent.py"
    shutil.copy2(adapter_path, adapter_dest)

    if gateway_adapter_path and gateway_adapter_path.exists():
        shutil.copy2(gateway_adapter_path, bundle_dir / f"{agent_id}_gateway_adapter_agent.py")
    else:
        gw_dest = scaffold_gateway_adapter(agent_meta, bundle_dir)

    if agent_meta.get("prompt_file") and Path(agent_meta["prompt_file"]).exists():
        shutil.copy2(agent_meta["prompt_file"], bundle_dir / "AGENTS.md")

    if agent_meta.get("config_path") and Path(agent_meta["config_path"]).exists():
        shutil.copy2(agent_meta["config_path"], bundle_dir / "openclaw.json")

    manifest = {
        "agent_id": agent_id,
        "task_ref": last_run.get("task_ref", ""),
        "seed": last_run.get("seed", 0),
        "harness_version": harness_version,
        "run_id": last_run.get("run_id", ""),
        "passed_at": last_run.get("finished_at") or last_run.get("started_at", ""),
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    readme = _generate_readme(agent_id, manifest)
    (bundle_dir / "README.md").write_text(readme, encoding="utf-8")
    return bundle_dir


def _generate_readme(agent_id: str, manifest: dict) -> str:
    return f"""# TraceCore Export: {agent_id}

Certified TraceCore adapter bundle for OpenClaw agent `{agent_id}`.

> **Note:** These adapters are for **optional regression testing** against TraceCore's
> deterministic harness — not for deploying your OpenClaw agent. Your agent continues
> to run normally in OpenClaw. Use these to verify your agent's behaviour against
> reproducible benchmark tasks before or after changes.

## Certification

| Field | Value |
|---|---|
| Agent ID | `{manifest["agent_id"]}` |
| Task | `{manifest["task_ref"]}` |
| Seed | `{manifest["seed"]}` |
| Harness version | `{manifest["harness_version"]}` |
| Run ID | `{manifest["run_id"]}` |
| Certified at | `{manifest["passed_at"]}` |

## Usage

```bash
# Regression test with the self-contained adapter (no OpenClaw install needed)
agent-bench run --agent {agent_id}_adapter_agent.py --task {manifest["task_ref"]} --seed {manifest["seed"]}

# Regression test with the gateway adapter (runs against your live OpenClaw model)
# Wire up your gateway client in {agent_id}_gateway_adapter_agent.py, then:
agent-bench run --agent {agent_id}_gateway_adapter_agent.py --task {manifest["task_ref"]} --seed {manifest["seed"]}
```

## Files

- `{agent_id}_adapter_agent.py` — self-contained regression adapter, tested and certified
- `{agent_id}_gateway_adapter_agent.py` — gateway adapter for regression testing against your live OpenClaw model
- `AGENTS.md` — original OpenClaw prompt file
- `openclaw.json` — original OpenClaw agent config
- `manifest.json` — certification metadata
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_class_name(agent_id: str) -> str:
    return "".join(part.capitalize() for part in agent_id.replace("-", "_").split("_"))
