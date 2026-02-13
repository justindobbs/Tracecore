"""Minimal FastAPI UI wrapper for Agent Bench."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from agent_bench.runner.baseline import build_baselines, load_latest_baseline
from agent_bench.runner.runlog import list_runs, load_run, persist_run
from agent_bench.runner.runner import run

TEMPLATES_DIR = Path(__file__).with_suffix("").with_name("templates")
TASKS_ROOT = Path("tasks")
AGENTS_ROOT = Path("agents")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app = FastAPI(title="Agent Bench UI", version="0.1.0")


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


def get_task_options() -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if not TASKS_ROOT.exists():
        return options
    for task_dir in sorted(TASKS_ROOT.iterdir()):
        yaml_path = task_dir / "task.yaml"
        if not yaml_path.exists():
            continue
        meta = _parse_task_yaml(yaml_path)
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
    recent_runs = list_runs(limit=8)
    baselines = build_baselines(max_runs=400)
    published_baseline = load_latest_baseline()
    selected_task_ref = extra.get("selected_task")
    if selected_task_ref is None and tasks:
        selected_task_ref = tasks[0]["ref"]
    selected_task_meta = next((t for t in tasks if t["ref"] == selected_task_ref), None)
    extra = dict(extra)
    extra.pop("selected_task", None)
    base = {
        "request": request,
        "tasks": tasks,
        "agents": agents,
        "selected_task": selected_task_ref,
        "selected_task_meta": selected_task_meta,
        "recent_runs": recent_runs,
        "baselines": baselines,
        "published_baseline": published_baseline,
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    trace_id = request.query_params.get("trace_id")
    trace_run, trace_error = _load_trace(trace_id)
    return templates.TemplateResponse(
        "index.html",
        _template_context(request, trace_run=trace_run, trace_error=trace_error, trace_id=trace_id),
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
