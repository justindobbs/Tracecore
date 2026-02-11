"""Minimal FastAPI UI wrapper for Agent Bench."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
    selected_task_ref = extra.get("selected_task")
    if selected_task_ref is None and tasks:
        selected_task_ref = tasks[0]["ref"]
    selected_task_meta = next((t for t in tasks if t["ref"] == selected_task_ref), None)
    base = {
        "request": request,
        "tasks": tasks,
        "agents": agents,
        "selected_task": selected_task_ref,
        "selected_task_meta": selected_task_meta,
    }
    base.update(extra)
    return base


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", _template_context(request))


@app.post("/run", response_class=HTMLResponse)
async def run_task(
    request: Request,
    agent: str = Form(...),
    task: str = Form(...),
    seed: int = Form(0),
) -> HTMLResponse:
    result: dict[str, Any] | None = None
    error: str | None = None
    try:
        result = run(agent, task, seed=seed)
    except Exception as exc:  # pragma: no cover - defensive for UI feedback
        error = str(exc)
    return templates.TemplateResponse(
        "index.html",
        _template_context(
            request,
            selected_agent=agent,
            selected_task=task,
            selected_seed=seed,
            result=result,
            error=error,
        ),
    )
