"""Minimal FastAPI UI wrapper for TraceCore."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from agent_bench.ledger import list_entries
from agent_bench.pairings import list_pairings
from agent_bench.runner.baseline import build_baselines, diff_runs, load_latest_baseline, load_run_artifact
from agent_bench.runner.failures import FAILURE_TYPES
from agent_bench.runner.runlog import list_runs, load_run, persist_run
from agent_bench.runner.runner import run

TEMPLATES_DIR = Path(__file__).with_suffix("").with_name("templates")
TASKS_ROOT = Path("tasks")
AGENTS_ROOT = Path("agents")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app = FastAPI(title="TraceCore UI", version="0.7.0")

GUIDE_ENTRIES = [
    {
        "agent": "agents/toy_agent.py",
        "success": ["filesystem_hidden_config@1"],
        "notes": "Filesystem discovery reference; should succeed on the hidden config task.",
    },
    {
        "agent": "agents/naive_llm_agent.py",
        "success": ["filesystem_hidden_config@1"],
        "notes": "Minimal baseline; may fail if retries are exhausted.",
    },
    {
        "agent": "agents/rate_limit_agent.py",
        "success": ["rate_limited_api@1"],
        "notes": "Rate-limit retry flow reference; tuned for the API task.",
    },
    {
        "agent": "agents/chain_agent.py",
        "success": ["rate_limited_chain@1", "deterministic_rate_service@1"],
        "notes": "Handshake + rate-limit reference; should solve chained API tasks.",
    },
    {
        "agent": "agents/planner_agent.py",
        "success": ["rate_limited_chain@1"],
        "notes": "Planner-style scaffold; may fail depending on budgets or drift.",
    },
    {
        "agent": "agents/ops_triage_agent.py",
        "success": [
            "log_alert_triage@1",
            "config_drift_remediation@1",
            "incident_recovery_chain@1",
        ],
        "notes": "Operations triage reference; should succeed on ops suite tasks.",
    },
    {
        "agent": "agents/log_stream_monitor_agent.py",
        "success": ["log_stream_monitor@1"],
        "notes": "Log stream patrol reference; polls pages, ignores noise, fires on CRITICAL entry.",
    },
    {
        "agent": "agents/cheater_agent.py",
        "success": [],
        "notes": "Expected to fail with sandbox violation; use for defense checks.",
    },
]


def _parse_task_yaml(path: Path) -> dict[str, Any]:
    # Reuse loader-like parsing to avoid external YAML dependency.
    text = path.read_text(encoding="utf-8").splitlines()
    data: dict[str, Any] = {}
    i = 0
    while i < len(text):
        line = text[i].rstrip()
        i += 1
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("description:") and line.endswith("|"):
            desc_lines = []
            while i < len(text):
                raw = text[i]
                if not raw.startswith("  "):
                    break
                desc_lines.append(raw[2:])
                i += 1
            data["description"] = "\n".join(desc_lines).strip()
            continue
        if line.startswith("default_budget:"):
            budget = {}
            while i < len(text):
                raw = text[i]
                if not raw.startswith("  "):
                    break
                key, val = raw.strip().split(":", 1)
                budget[key.strip()] = int(val.strip())
                i += 1
            data["default_budget"] = budget
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key == "version":
                data[key] = int(val)
            else:
                data[key] = val
    return data


def _parse_task_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib  # type: ignore[attr-defined]
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[assignment]
    return tomllib.loads(path.read_text(encoding="utf-8"))


def get_task_options() -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if not TASKS_ROOT.exists():
        return options
    for task_dir in sorted(TASKS_ROOT.iterdir()):
        toml_path = task_dir / "task.toml"
        yaml_path = task_dir / "task.yaml"
        if toml_path.exists():
            meta = _parse_task_toml(toml_path)
        elif yaml_path.exists():
            meta = _parse_task_yaml(yaml_path)
        else:
            continue
        if meta.get("internal"):
            continue
        entry = {
            "id": meta.get("id", task_dir.name),
            "suite": meta.get("suite", ""),
            "version": meta.get("version", 1),
            "description": meta.get("description", ""),
        }
        entry["ref"] = f"{entry['id']}@{entry['version']}"
        options.append(entry)
    return options


def get_agent_options() -> list[str]:
    if not AGENTS_ROOT.exists():
        return []
    return [str(path).replace("\\", "/") for path in sorted(AGENTS_ROOT.glob("*.py"))]


def _template_context(request: Request, **extra: Any) -> dict[str, Any]:
    tasks = get_task_options()
    agents = get_agent_options()
    recent_filters = extra.pop("recent_filters", None) or {}
    baseline_filters = extra.pop("baseline_filters", None) or {}
    recent_runs = list_runs(
        limit=8,
        agent=recent_filters.get("agent"),
        task_ref=recent_filters.get("task_ref"),
        failure_type=recent_filters.get("failure_type"),
    )
    baselines = build_baselines(
        max_runs=400,
        agent=baseline_filters.get("agent"),
        task_ref=baseline_filters.get("task_ref"),
    )
    published_baseline = load_latest_baseline()
    selected_task_ref = extra.get("selected_task")
    if selected_task_ref is None and tasks:
        selected_task_ref = tasks[0]["ref"]
    selected_task_meta = next((t for t in tasks if t["ref"] == selected_task_ref), None)
    extra = dict(extra)
    extra.pop("selected_task", None)
    compare_inputs = extra.pop("compare_inputs", None) or {"run_a": "", "run_b": ""}
    pairing_cards = []
    for p in list_pairings():
        last = list_runs(agent=p.agent, task_ref=p.task, limit=1)
        last_run = last[0] if last else None
        pairing_cards.append({
            "name": p.name,
            "agent": p.agent,
            "task": p.task,
            "description": p.description,
            "last_run_id": last_run["run_id"] if last_run else None,
            "last_success": (last_run.get("failure_type") is None) if last_run else None,
            "last_seed": last_run.get("seed") if last_run else None,
        })
    base = {
        "request": request,
        "tasks": tasks,
        "agents": agents,
        "pairings": pairing_cards,
        "selected_task": selected_task_ref,
        "selected_task_meta": selected_task_meta,
        "recent_runs": recent_runs,
        "baselines": baselines,
        "published_baseline": published_baseline,
        "compare_diff": extra.get("compare_diff"),
        "compare_error": extra.get("compare_error"),
        "compare_inputs": compare_inputs,
        "recent_filters": recent_filters,
        "baseline_filters": baseline_filters,
        "failure_types": FAILURE_TYPES,
    }
    base.update(extra)
    return base


def _load_trace(run_id: str | None) -> tuple[dict | None, str | None]:
    if not run_id:
        return None, None
    try:
        return load_run(run_id), None
    except FileNotFoundError:
        return None, f"Trace {run_id} not found."
    except Exception as exc:
        return None, f"Failed to load trace: {exc}"


@app.get("/api/pairings")
async def api_pairings() -> JSONResponse:
    result = []
    for p in list_pairings():
        last = list_runs(agent=p.agent, task_ref=p.task, limit=1)
        last_run = last[0] if last else None
        result.append({
            "name": p.name,
            "agent": p.agent,
            "task": p.task,
            "description": p.description,
            "last_run_id": last_run["run_id"] if last_run else None,
            "last_success": (last_run.get("failure_type") is None) if last_run else None,
            "last_seed": last_run.get("seed") if last_run else None,
        })
    return JSONResponse(result)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    trace_id = request.query_params.get("trace_id")
    recent_filters = {
        "agent": request.query_params.get("recent_agent") or None,
        "task_ref": request.query_params.get("recent_task") or None,
        "failure_type": request.query_params.get("recent_failure") or None,
    }
    baseline_filters = {
        "agent": request.query_params.get("baseline_agent") or None,
        "task_ref": request.query_params.get("baseline_task") or None,
    }
    trace_run, trace_error = _load_trace(trace_id)
    return templates.TemplateResponse(
        "index.html",
        _template_context(
            request,
            trace_run=trace_run,
            trace_error=trace_error,
            trace_id=trace_id,
            recent_filters=recent_filters,
            baseline_filters=baseline_filters,
        ),
    )


@app.post("/run", response_class=HTMLResponse)
async def run_task(
    request: Request,
    agent: str = Form(""),
    task: str = Form(""),
    seed: int | None = Form(None),
    replay: str | None = Form(None),
) -> HTMLResponse:
    result: dict[str, Any] | None = None
    error: str | None = None
    trace_run: dict[str, Any] | None = None

    try:
        if replay:
            artifact = load_run(replay)
            recorded_agent = artifact.get("agent")
            recorded_task = artifact.get("task_ref")
            recorded_seed = artifact.get("seed", 0)

            agent = agent or recorded_agent or ""
            task = task or recorded_task or ""
            seed = recorded_seed if seed is None else seed

            if not agent or not task:
                raise ValueError("Replay requires artifact with agent/task or explicit overrides")
        else:
            if not agent or not task:
                raise ValueError("Agent and task are required (or provide a replay run_id)")
            seed = 0 if seed is None else seed

        result = run(agent, task, seed=seed)
        try:
            persist_run(result)
        except Exception as exc:  # pragma: no cover - best-effort logging
            error = f"run succeeded but failed to persist artifact: {exc}"
        trace_run = result
    except Exception as exc:  # pragma: no cover - defensive for UI feedback
        error = str(exc)

    return templates.TemplateResponse(
        "index.html",
        _template_context(
            request,
            selected_agent=agent,
            selected_task=task,
            selected_seed=seed if seed is not None else 0,
            result=result,
            error=error,
            trace_run=trace_run,
            trace_id=trace_run.get("run_id") if trace_run else None,
            result_download_id=trace_run.get("run_id") if trace_run else None,
        ),
    )


@app.get("/traces/{run_id}", response_class=HTMLResponse)
async def view_trace(request: Request, run_id: str) -> HTMLResponse:
    trace_run, trace_error = _load_trace(run_id)
    return templates.TemplateResponse(
        "index.html",
        _template_context(
            request,
            trace_run=trace_run,
            trace_error=trace_error,
            trace_id=run_id,
        ),
    )


@app.get("/api/traces/{run_id}", response_class=JSONResponse)
async def trace_api(run_id: str) -> JSONResponse:
    trace_run, trace_error = _load_trace(run_id)
    if trace_run:
        return JSONResponse(trace_run)
    status_code = 404 if "not found" in (trace_error or "").lower() else 500
    return JSONResponse({"error": trace_error or "unknown_error"}, status_code=status_code)


@app.get("/baselines/latest")
async def download_latest_baseline() -> FileResponse:
    payload = load_latest_baseline()
    if not payload:
        raise HTTPException(status_code=404, detail="No baseline export found")
    path = Path(payload["_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Baseline file missing")
    return FileResponse(path, media_type="application/json", filename=payload.get("_filename", path.name))


@app.get("/api/ledger", response_class=JSONResponse)
async def api_ledger() -> JSONResponse:
    return JSONResponse(list_entries())


@app.get("/ledger", response_class=HTMLResponse)
async def ledger(request: Request) -> HTMLResponse:
    entries = list_entries()
    return templates.TemplateResponse(
        "ledger.html",
        {
            "request": request,
            "entries": entries,
        },
    )


@app.get("/guide", response_class=HTMLResponse)
async def guide(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "guide.html",
        {
            "request": request,
            "guide_entries": GUIDE_ENTRIES,
        },
    )


@app.post("/compare", response_class=HTMLResponse)
async def compare_runs(request: Request, run_a: str = Form(""), run_b: str = Form("")) -> HTMLResponse:
    compare_error: str | None = None
    diff: dict | None = None
    try:
        if not run_a or not run_b:
            raise ValueError("Both run references are required")
        artifact_a = load_run_artifact(run_a)
        artifact_b = load_run_artifact(run_b)
        diff = diff_runs(artifact_a, artifact_b)
    except FileNotFoundError:
        compare_error = "One of the provided run references could not be found."
    except Exception as exc:  # pragma: no cover - defensive feedback
        compare_error = str(exc)

    return templates.TemplateResponse(
        "index.html",
        _template_context(
            request,
            compare_diff=diff,
            compare_error=compare_error,
            compare_inputs={"run_a": run_a, "run_b": run_b},
            selected_task=request.query_params.get("task"),
        ),
    )
