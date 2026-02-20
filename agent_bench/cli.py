"""CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_bench.config import AgentBenchConfig, ConfigError, load_config
from agent_bench.interactive import run_wizard
from agent_bench.pairings import find_pairing, list_pairings
from agent_bench.runner.baseline import (
    build_baselines,
    diff_runs,
    export_baseline,
    load_run_artifact,
)
from agent_bench.runner.failures import FAILURE_TYPES
from agent_bench.runner.runlog import list_runs, load_run, persist_run
from agent_bench.runner.runner import run
from agent_bench.tasks.registry import validate_registry_entries, validate_task_path
from agent_bench.webui.app import app
from agent_bench.maintainer import dumps_summary, maintain
from agent_bench.ledger import get_entry, list_entries


def _load_config_from_args(config_path: str | None) -> AgentBenchConfig | None:
    try:
        return load_config(config_path)
    except ConfigError as exc:
        raise SystemExit(str(exc))


def _resolve_run_inputs(
    args: argparse.Namespace,
    config: AgentBenchConfig | None,
    *,
    require_seed: bool = True,
) -> tuple[str | None, str | None, int | None]:
    agent = getattr(args, "agent", None)
    task = getattr(args, "task", None)
    seed = getattr(args, "seed", None) if require_seed else None

    if config:
        agent = agent or config.get_default_agent()
        if task is None:
            task = config.get_task(agent=agent)
        if task is None:
            task = config.get_default_task()
        if require_seed and seed is None:
            seed = config.get_seed(agent=agent)
    return agent, task, seed


def _run_with_timeout(agent: str, task: str, seed: int, timeout: int | None) -> dict:
    """Run agent+task, enforcing a wall-clock timeout (seconds) if given."""
    if timeout is None:
        return run(agent, task, seed=seed)

    import threading
    result_box: list[dict] = []
    exc_box: list[BaseException] = []

    def _target() -> None:
        try:
            result_box.append(run(agent, task, seed=seed))
        except BaseException as exc:  # noqa: BLE001
            exc_box.append(exc)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise SystemExit(f"run timed out after {timeout}s (agent={agent}, task={task}, seed={seed})")
    if exc_box:
        raise exc_box[0]
    return result_box[0]


def _cmd_run(args: argparse.Namespace) -> int:
    config = getattr(args, "_config", None)
    timeout: int | None = getattr(args, "timeout", None)
    if args.replay:
        artifact = load_run(args.replay)
        recorded_agent = artifact.get("agent")
        recorded_task = artifact.get("task_ref")
        recorded_seed = artifact.get("seed", 0)

        agent = args.agent or recorded_agent
        task = args.task or recorded_task
        seed = args.seed if args.seed is not None else recorded_seed

        if not agent or not task:
            raise SystemExit("replay requires an artifact with agent/task or explicit overrides")

        if agent != recorded_agent or task != recorded_task or seed != recorded_seed:
            print(
                "warning: overriding recorded artifact values for replay "
                f"(run_id={args.replay}, agent={recorded_agent}, task={recorded_task}, seed={recorded_seed})",
                file=sys.stderr,
            )
    else:
        agent, task, seed = _resolve_run_inputs(args, config)
        if not agent or not task:
            raise SystemExit(
                "agent and task are required unless using --replay (set CLI flags or defaults in agent-bench.toml)"
            )
        seed = 0 if seed is None else seed

    result = _run_with_timeout(agent, task, seed, timeout)
    try:
        persist_run(result)
    except Exception as exc:  # pragma: no cover - logging failure shouldn't abort run
        print(f"warning: failed to persist run artifact ({exc})", file=sys.stderr)
    print(json.dumps(result, indent=2))
    _print_run_summary(result)
    return 0


def _print_run_summary(result: dict) -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        console = Console(stderr=True)
        success = result.get("failure_type") is None
        steps = result.get("steps_used", "?")
        tool_calls = result.get("tool_calls_used", "?")
        task_ref = result.get("task_ref", "?")
        failure_type = result.get("failure_type")
        failure_reason = result.get("failure_reason")
        if success:
            detail = f"[bold green]✓ SUCCESS[/bold green]  {task_ref}  |  steps: {steps}  tool_calls: {tool_calls}"
            console.print(Panel(detail, border_style="green"))
        else:
            ft = f"  failure_type: [yellow]{failure_type}[/yellow]" if failure_type else ""
            fr = f"\n  reason: [dim]{failure_reason}[/dim]" if failure_reason else ""
            detail = f"[bold red]✗ FAILED[/bold red]  {task_ref}  |  steps: {steps}  tool_calls: {tool_calls}{ft}{fr}"
            console.print(Panel(detail, border_style="red"))
    except Exception:
        pass


def _cmd_runs_list(args: argparse.Namespace) -> int:
    runs = list_runs(
        agent=args.agent,
        task_ref=args.task,
        limit=args.limit,
        failure_type=args.failure_type,
    )
    print(json.dumps(runs, indent=2))
    return 0


def _cmd_runs_summary(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table
    runs = list_runs(
        agent=args.agent,
        task_ref=args.task,
        limit=args.limit,
        failure_type=args.failure_type,
    )
    console = Console()
    if not runs:
        console.print("[dim]No runs found.[/dim]")
        return 0
    table = Table(box=None, padding=(0, 1), show_header=True)
    table.add_column("Outcome", no_wrap=True)
    table.add_column("Agent", style="bright_white", no_wrap=True)
    table.add_column("Task", style="magenta", no_wrap=True)
    table.add_column("Seed", style="dim", no_wrap=True)
    table.add_column("Steps", style="dim", no_wrap=True)
    table.add_column("Tool calls", style="dim", no_wrap=True)
    table.add_column("Run ID", style="dim", no_wrap=True)
    for r in runs:
        success = r.get("failure_type") is None
        outcome = "[green]✓ success[/green]" if success else f"[red]✗ {r.get('failure_type', 'failed')}[/red]"
        agent_short = r.get("agent", "").replace("agents/", "")
        table.add_row(
            outcome,
            agent_short,
            r.get("task_ref", ""),
            str(r.get("seed", "?")),
            str(r.get("steps_used", "?")),
            str(r.get("tool_calls_used", "?")),
            (r.get("run_id") or "")[:12],
        )
    console.print()
    console.print(table)
    console.print()
    return 0


def _compare_exit_code(diff: dict) -> int:
    summary = diff.get("summary", {})
    same_agent = bool(summary.get("same_agent"))
    same_task = bool(summary.get("same_task"))
    if not same_agent or not same_task:
        return 2
    if diff.get("step_diffs"):
        return 1
    if not summary.get("same_success"):
        return 1
    steps = summary.get("steps", {})
    tools = summary.get("tool_calls", {})
    if steps.get("run_a") != steps.get("run_b"):
        return 1
    if tools.get("run_a") != tools.get("run_b"):
        return 1
    return 0


def _print_diff_text(diff: dict, exit_code: int) -> None:
    summary = diff.get("summary", {})
    run_a = diff.get("run_a", {})
    run_b = diff.get("run_b", {})

    status = "identical"
    if exit_code == 2:
        status = "incompatible"
    elif exit_code == 1:
        status = "different"

    print(f"Compare: {status}")
    print(f"Agent A: {run_a.get('agent')}")
    print(f"Agent B: {run_b.get('agent')}")
    print(f"Task A: {run_a.get('task_ref')}")
    print(f"Task B: {run_b.get('task_ref')}")
    print(f"Success A: {run_a.get('success')}")
    print(f"Success B: {run_b.get('success')}")
    print(f"Steps A: {summary.get('steps', {}).get('run_a')}")
    print(f"Steps B: {summary.get('steps', {}).get('run_b')}")
    print(f"Tool calls A: {summary.get('tool_calls', {}).get('run_a')}")
    print(f"Tool calls B: {summary.get('tool_calls', {}).get('run_b')}")

    step_diffs = diff.get("step_diffs") or []
    if step_diffs:
        first = step_diffs[0]
        print(f"First divergence: step {first.get('step')}")


def _cmd_baseline(args: argparse.Namespace) -> int:
    config = getattr(args, "_config", None)
    compare = getattr(args, "compare", None)
    if compare:
        run_a = load_run_artifact(compare[0])
        run_b = load_run_artifact(compare[1])
        diff = diff_runs(run_a, run_b)
        exit_code = _compare_exit_code(diff)
        if args.format == "text":
            _print_diff_text(diff, exit_code)
        else:
            print(json.dumps(diff, indent=2))
        return exit_code
    agent, task, _ = _resolve_run_inputs(args, config, require_seed=False)
    rows = build_baselines(agent=agent, task_ref=task, max_runs=args.limit)
    payload: object = rows
    if args.export is not None:
        target = None if args.export == "" else args.export
        meta = {
            "agent_filter": agent,
            "task_filter": task,
            "limit": args.limit,
        }
        path = export_baseline(rows, path=target, metadata=meta)
        payload = {"rows": rows, "export_path": str(path)}
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_run_pairing(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table
    console = Console()

    if getattr(args, "list", False):
        table = Table(title="Known Pairings", box=None, padding=(0, 1))
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Agent", style="bright_white", no_wrap=True)
        table.add_column("Task", style="magenta", no_wrap=True)
        table.add_column("Description", style="green")
        for p in list_pairings():
            table.add_row(p.name, p.agent, p.task, p.description)
        console.print()
        console.print(table)
        console.print()
        return 0

    if getattr(args, "all", False):
        return _cmd_run_pairing_all(args)

    name = getattr(args, "pairing_name", None)
    pairing = find_pairing(name, cwd=Path.cwd())

    if pairing is None:
        console.print("[bold red]No pairing found.[/bold red]")
        if name:
            console.print(f"  '[yellow]{name}[/yellow]' does not match any known pairing.")
        else:
            console.print(
                "  Navigate to a directory containing a paired agent file, or specify a name:\n"
                "  [cyan]agent-bench run pairing log_stream_monitor[/cyan]\n"
                "  Run [cyan]agent-bench run pairing --list[/cyan] to see all available pairings."
            )
        return 1

    seed = args.seed if args.seed is not None else 0
    console.print(f"[dim]Pairing:[/dim] [cyan]{pairing.name}[/cyan]  "
                  f"[dim]agent:[/dim] {pairing.agent}  "
                  f"[dim]task:[/dim] {pairing.task}  "
                  f"[dim]seed:[/dim] {seed}")
    run_args = argparse.Namespace(
        agent=pairing.agent,
        task=pairing.task,
        seed=seed,
        replay=None,
        timeout=getattr(args, "timeout", None),
        _config=getattr(args, "_config", None),
    )
    return _cmd_run(run_args)


def _cmd_run_pairing_all(args: argparse.Namespace) -> int:
    from rich.console import Console
    from rich.table import Table
    console = Console()
    seed = args.seed if args.seed is not None else 0
    timeout: int | None = getattr(args, "timeout", None)
    pairings = list_pairings()

    console.print(f"\n[bold]Running {len(pairings)} pairings[/bold]  seed={seed}\n")

    rows: list[tuple] = []
    any_failed = False
    for p in pairings:
        console.print(f"  [dim]→[/dim] [cyan]{p.name}[/cyan]  {p.agent}  {p.task} ...", end="")
        try:
            result = _run_with_timeout(p.agent, p.task, seed, timeout)
            try:
                persist_run(result)
            except Exception:  # pragma: no cover
                pass
            success = result.get("failure_type") is None
            outcome = "[green]✓ success[/green]" if success else f"[red]✗ {result.get('failure_type', 'failed')}[/red]"
            rows.append((
                outcome,
                p.name,
                str(result.get("steps_used", "?")),
                str(result.get("tool_calls_used", "?")),
                result.get("failure_reason") or "",
            ))
            if not success:
                any_failed = True
        except SystemExit as exc:
            rows.append(("[red]✗ timeout[/red]", p.name, "—", "—", str(exc)))
            any_failed = True
        except Exception as exc:  # noqa: BLE001
            rows.append(("[red]✗ error[/red]", p.name, "—", "—", str(exc)))
            any_failed = True
        console.print(" " + rows[-1][0])

    table = Table(title="Pairing Smoke-Test Results", box=None, padding=(0, 1))
    table.add_column("Outcome", no_wrap=True)
    table.add_column("Pairing", style="cyan", no_wrap=True)
    table.add_column("Steps", style="dim", no_wrap=True)
    table.add_column("Tool calls", style="dim", no_wrap=True)
    table.add_column("Note", style="dim")
    for row in rows:
        table.add_row(*row)
    console.print()
    console.print(table)
    console.print()
    return 1 if any_failed else 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_interactive(args: argparse.Namespace) -> int:
    config = getattr(args, "_config", None)
    selection = run_wizard(
        config=config,
        no_color=args.no_color,
        save_session=args.save_session,
        include_plugins=args.plugins,
        dry_run=args.dry_run,
    )
    if selection is None:
        return 0 if args.dry_run else 1
    agent, task, seed = selection
    run_args = argparse.Namespace(
        agent=agent,
        task=task,
        seed=seed,
        replay=None,
        _config=config,
    )
    return _cmd_run(run_args)


def _cmd_tasks_validate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    paths = getattr(args, "path", None) or []
    if not paths and not args.registry:
        args.registry = True

    for raw_path in paths:
        path = Path(raw_path)
        path_errors = validate_task_path(path)
        if path_errors:
            for err in path_errors:
                errors.append(f"{path}: {err}")

    if args.registry:
        errors.extend(validate_registry_entries())

    payload = {"valid": not errors, "errors": errors}
    print(json.dumps(payload, indent=2))
    return 0 if not errors else 1


def _cmd_new_agent(args: argparse.Namespace) -> int:
    from rich.console import Console
    console = Console()

    raw_name: str = args.name
    class_name = "".join(part.capitalize() for part in raw_name.replace("-", "_").split("_")) + "Agent"
    file_name = raw_name.replace("-", "_") + "_agent.py"
    output_dir = Path(args.output_dir) if args.output_dir else Path("agents")
    target = output_dir / file_name

    if target.exists() and not args.force:
        console.print(f"[bold red]Error:[/bold red] {target} already exists. Use [cyan]--force[/cyan] to overwrite.")
        return 1

    stub = f'''"""Agent stub generated by `agent-bench new-agent {raw_name}`."""

from __future__ import annotations


class {class_name}:
    """Stub agent implementing the reset / observe / act interface.

    Replace the placeholder logic in `act()` with your agent's decision loop.
    """

    def __init__(self) -> None:
        self.reset({{}})

    def reset(self, task_spec) -> None:
        """Called once before each episode. Store task_spec for later use."""
        self.task_spec = task_spec or {{}}
        self.obs = None
        self.step = 0

    def observe(self, observation) -> None:
        """Receive the latest environment observation."""
        self.obs = observation

    def act(self) -> dict:
        """Return the next action dict.

        Every action must have at minimum:
            {{"type": "<action_type>", "args": {{...}}}}

        Use {{"type": "set_output", "args": {{"key": ..., "value": ...}}}} to
        submit the final answer and end the episode successfully.

        Use {{"type": "wait", "args": {{}}}} to consume a step without acting.
        """
        self.step += 1

        if self.obs is None:
            return {{"type": "wait", "args": {{}}}}

        remaining_steps = self.obs.get("remaining_steps", 0)
        remaining_tool_calls = self.obs.get("remaining_tool_calls", 0)

        if remaining_steps <= 1 or remaining_tool_calls <= 1:
            return {{"type": "wait", "args": {{}}}}

        # TODO: implement your agent logic here
        return {{"type": "wait", "args": {{}}}}
'''

    output_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(stub, encoding="utf-8")
    console.print(f"[green]Created[/green] {target}")
    console.print(f"  Class:  [cyan]{class_name}[/cyan]")
    console.print(f"  Run it: [dim]agent-bench run --agent {target} --task <task_ref> --seed 0[/dim]")
    return 0


def _cmd_openclaw(args: argparse.Namespace) -> int:
    from rich.console import Console
    from agent_bench.openclaw import (
        detect_openclaw_agent,
        scaffold_openclaw_adapter,
        scaffold_gateway_adapter,
    )

    console = Console(stderr=True)
    cwd = Path.cwd()
    agent_id: str | None = getattr(args, "agent_id", None)
    gateway: bool = getattr(args, "gateway", False)

    meta = detect_openclaw_agent(cwd, agent_id)
    if meta is None:
        console.print("[bold red]Error:[/bold red] No OpenClaw agent found.")
        if agent_id:
            console.print(f"  Agent '[yellow]{agent_id}[/yellow]' not in openclaw.json.")
        else:
            console.print(
                "  No openclaw.json found in CWD or ~/.openclaw/. "
                "Navigate to your OpenClaw workspace or pass [cyan]--agent-id <id>[/cyan]."
            )
        return 1

    console.print(f"[dim]Detected OpenClaw agent:[/dim] [cyan]{meta['id']}[/cyan]")
    if meta.get("prompt_file"):
        console.print(f"  Prompt file: [dim]{meta['prompt_file']}[/dim]")
    if (meta.get("model") or {}).get("primary"):
        console.print(f"  Model: [dim]{meta['model']['primary']}[/dim]")

    config_dir = Path(meta["config_path"]).parent
    out_dir = config_dir / "tracecore_adapters"
    adapter_path = out_dir / f"{meta['id']}_adapter_agent.py"

    if not adapter_path.exists():
        adapter_path = scaffold_openclaw_adapter(meta, out_dir)
        console.print(f"[green]Scaffolded[/green] {adapter_path}")
        if gateway:
            gw_path = scaffold_gateway_adapter(meta, out_dir)
            console.print(f"[green]Scaffolded[/green] {gw_path} [dim](gateway)[/dim]")
        console.print(
            f"  Edit [cyan]tracecore_adapters/{adapter_path.name}[/cyan] then re-run "
            "[dim]agent-bench openclaw[/dim] to test."
        )
        return 0

    task_ref: str = getattr(args, "task", None) or "filesystem_hidden_config@1"
    seed: int = getattr(args, "seed", None) or 0
    console.print(
        f"[dim]Running:[/dim] {adapter_path.name}  "
        f"[dim]task:[/dim] {task_ref}  [dim]seed:[/dim] {seed}"
    )
    run_args = argparse.Namespace(
        agent=str(adapter_path),
        task=task_ref,
        seed=seed,
        replay=None,
        timeout=getattr(args, "timeout", None),
        _config=getattr(args, "_config", None),
    )
    return _cmd_run(run_args)


def _cmd_openclaw_export(args: argparse.Namespace) -> int:
    from rich.console import Console
    from agent_bench.openclaw import (
        detect_openclaw_agent,
        export_openclaw_agent,
    )

    console = Console(stderr=True)
    cwd = Path.cwd()
    agent_id: str | None = getattr(args, "agent_id", None)
    meta = detect_openclaw_agent(cwd, agent_id)
    if meta is None:
        console.print("[bold red]Error:[/bold red] No OpenClaw agent found. Run [cyan]agent-bench openclaw[/cyan] first.")
        return 1

    config_dir = Path(meta["config_path"]).parent
    out_dir_arg = getattr(args, "out_dir", None)
    if out_dir_arg:
        out_dir = Path(out_dir_arg).resolve()
    else:
        out_dir = config_dir / "tracecore_export"

    adapter_path = config_dir / "tracecore_adapters" / f"{meta['id']}_adapter_agent.py"
    if not adapter_path.exists():
        console.print(f"[bold red]Error:[/bold red] Adapter not found: {adapter_path}")
        console.print("  Run [cyan]agent-bench openclaw[/cyan] to scaffold and test it first.")
        return 1

    last_runs = list_runs(agent=str(adapter_path), limit=1)
    passing = [r for r in last_runs if r.get("failure_type") is None]
    if not passing:
        console.print("[bold red]Error:[/bold red] No passing run found for this adapter.")
        console.print(
            "  Test it first: [cyan]agent-bench openclaw "
            f"--agent-id {meta['id']}[/cyan]"
        )
        return 1

    last_run = passing[0]

    gw_path = config_dir / "tracecore_adapters" / f"{meta['id']}_gateway_adapter_agent.py"
    if not gw_path.exists():
        gw_path = None

    bundle_dir = export_openclaw_agent(
        agent_meta=meta,
        adapter_path=adapter_path,
        last_run=last_run,
        out_dir=out_dir,
        gateway_adapter_path=gw_path,
    )
    console.print(f"[green]Exported[/green] {bundle_dir}")
    console.print(f"  Run ID: [dim]{last_run.get('run_id', '?')}[/dim]")
    console.print(f"  Task:   [dim]{last_run.get('task_ref', '?')}[/dim]")
    return 0


def _cmd_ledger(args: argparse.Namespace) -> int:
    show = getattr(args, "show", None)
    if show:
        entry = get_entry(show)
        if entry is None:
            print(f"No ledger entry found for {show!r}", file=sys.stderr)
            return 1
        print(json.dumps(entry, indent=2))
        return 0
    entries = list_entries()
    if not entries:
        print("Ledger is empty.", file=sys.stderr)
        return 0
    for entry in entries:
        tasks = entry.get("tasks", [])
        task_summary = ", ".join(t["task_ref"] for t in tasks)
        print(f"{entry['agent']}  [{entry.get('suite', '?')}]  {task_summary}")
    return 0


def _cmd_maintain(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    payload = maintain(
        cwd=cwd,
        pytest_args=args.pytest_args or getattr(args, "_passthrough", None),
        validate_tasks=not args.no_tasks_validate,
        fix_agent_files=args.fix_agent or [],
        dry_run=not args.apply,
    )
    print(dumps_summary(payload))
    return 0 if payload.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="agent-bench", add_help=True)
    parser.add_argument("--config", help="Path to agent-bench.toml (defaults to ./agent-bench.toml)")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run an agent against a task")
    run_sub = run_parser.add_subparsers(dest="run_command")

    pairing_parser = run_sub.add_parser("pairing", help="Run a known-good agent+task pairing by name")
    pairing_parser.add_argument(
        "pairing_name",
        nargs="?",
        help="Pairing name (e.g., log_stream_monitor); omit to auto-detect from CWD",
    )
    pairing_parser.add_argument("--seed", type=int, help="Deterministic seed (defaults to 0)")
    pairing_parser.add_argument("--list", action="store_true", help="List all available pairings and exit")
    pairing_parser.add_argument("--all", action="store_true", help="Run every pairing in sequence and print a summary table")
    pairing_parser.add_argument("--timeout", type=int, metavar="SECONDS", help="Wall-clock timeout per run in seconds")
    pairing_parser.set_defaults(func=_cmd_run_pairing)

    run_parser.add_argument("--agent", help="Path to the agent module")
    run_parser.add_argument("--task", help="Task reference (e.g., filesystem_hidden_config@1)")
    run_parser.add_argument("--seed", type=int, help="Deterministic seed (defaults to 0)")
    run_parser.add_argument(
        "--replay",
        help="Replay a prior run_id; agent/task/seed default to recorded values and can be overridden",
    )
    run_parser.add_argument("--timeout", type=int, metavar="SECONDS", help="Wall-clock timeout in seconds; exits non-zero if exceeded")
    run_parser.set_defaults(func=_cmd_run)

    runs_parser = subparsers.add_parser("runs", help="Inspect stored run artifacts")
    runs_sub = runs_parser.add_subparsers(dest="runs_command")
    runs_list = runs_sub.add_parser("list", help="List recent runs (newest first)")
    runs_list.add_argument("--agent", help="Filter by agent path")
    runs_list.add_argument("--task", dest="task", help="Filter by task reference")
    runs_list.add_argument("--limit", type=int, default=20, help="Maximum runs to return")
    runs_list.add_argument(
        "--failure-type",
        choices=("success",) + FAILURE_TYPES,
        help="Filter by failure type (or 'success' for completed runs)",
    )
    runs_list.set_defaults(func=_cmd_runs_list)

    runs_summary = runs_sub.add_parser("summary", help="Print a compact table of recent runs")
    runs_summary.add_argument("--agent", help="Filter by agent path")
    runs_summary.add_argument("--task", dest="task", help="Filter by task reference")
    runs_summary.add_argument("--limit", type=int, default=20, help="Maximum runs to show (default: 20)")
    runs_summary.add_argument(
        "--failure-type",
        dest="failure_type",
        choices=("success",) + FAILURE_TYPES,
        help="Filter by outcome",
    )
    runs_summary.set_defaults(func=_cmd_runs_summary)

    baseline_parser = subparsers.add_parser("baseline", help="Compute baseline stats from persisted runs")
    baseline_parser.add_argument("--agent", help="Filter by agent path")
    baseline_parser.add_argument("--task", dest="task", help="Filter by task reference")
    baseline_parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of runs to consider per filter (newest first)",
    )
    baseline_parser.add_argument(
        "--export",
        nargs="?",
        const="",
        help="Persist the baseline to .agent_bench/baselines (optionally supply relative path)",
    )
    baseline_parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("RUN_A", "RUN_B"),
        help="Diff two run artifacts (paths or run_ids) instead of computing aggregate stats",
    )
    baseline_parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format for --compare (default: json)",
    )
    baseline_parser.set_defaults(func=_cmd_baseline)

    ledger_parser = subparsers.add_parser("ledger", help="Inspect TraceCore Ledger entries")
    ledger_parser.add_argument(
        "--show",
        metavar="AGENT",
        help="Show detailed entry for AGENT (path or stem)",
    )
    ledger_parser.set_defaults(func=_cmd_ledger)

    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the web UI dashboard (FastAPI/uvicorn)")
    dashboard_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    dashboard_parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    dashboard_parser.add_argument("--reload", action="store_true", help="Enable autoreload (dev only)")
    dashboard_parser.set_defaults(func=_cmd_dashboard)

    interactive_parser = subparsers.add_parser(
        "interactive",
        help="Launch a colorful wizard to pick agent/task/seed before running",
    )
    interactive_parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors for the interactive wizard",
    )
    interactive_parser.add_argument(
        "--save-session",
        action="store_true",
        help="Save agent/task/seed selections to .agent_bench/.wizard_session.json for future runs",
    )
    interactive_parser.add_argument(
        "--plugins",
        action="store_true",
        help="Include plugin tasks in discovery (default: bundled tasks only)",
    )
    interactive_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the command without executing it",
    )
    interactive_parser.set_defaults(func=_cmd_interactive)

    tasks_parser = subparsers.add_parser("tasks", help="Inspect and validate task metadata")
    tasks_sub = tasks_parser.add_subparsers(dest="tasks_command")
    tasks_validate = tasks_sub.add_parser("validate", help="Validate task manifests and registry entries")
    tasks_validate.add_argument(
        "--path",
        action="append",
        help="Path to a task directory (repeatable)",
    )
    tasks_validate.add_argument(
        "--registry",
        action="store_true",
        help="Validate all registry entries (including plugins)",
    )
    tasks_validate.set_defaults(func=_cmd_tasks_validate)

    maintain_parser = subparsers.add_parser(
        "maintain",
        help="Run task validation + pytest and optionally apply guarded fixes",
    )
    maintain_parser.add_argument(
        "--cwd",
        help="Working directory to run checks from (default: current directory)",
    )
    maintain_parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        help="Additional args passed to pytest (prefix with --)",
    )
    maintain_parser.add_argument(
        "--no-tasks-validate",
        action="store_true",
        help="Skip agent-bench tasks validate --registry",
    )
    maintain_parser.add_argument(
        "--fix-agent",
        action="append",
        help="Agent file path to apply guarded fixers to (repeatable)",
    )
    maintain_parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply fixes in-place (default: dry-run)",
    )
    maintain_parser.set_defaults(func=_cmd_maintain)

    new_agent_parser = subparsers.add_parser(
        "new-agent",
        help="Scaffold a new agent stub with the correct reset/observe/act interface",
    )
    new_agent_parser.add_argument(
        "name",
        help="Agent name in snake_case or kebab-case (e.g., my_agent or my-agent)",
    )
    new_agent_parser.add_argument(
        "--output-dir",
        default="agents",
        metavar="DIR",
        help="Directory to write the stub into (default: agents/)",
    )
    new_agent_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing file",
    )
    new_agent_parser.set_defaults(func=_cmd_new_agent)

    openclaw_parser = subparsers.add_parser(
        "openclaw",
        help="Scaffold and test a TraceCore adapter for an OpenClaw agent",
    )
    openclaw_parser.add_argument(
        "--agent-id",
        dest="agent_id",
        metavar="ID",
        help="OpenClaw agent ID from openclaw.json (auto-detected if only one agent exists)",
    )
    openclaw_parser.add_argument(
        "--task",
        default="filesystem_hidden_config@1",
        help="Task ref to test against (default: filesystem_hidden_config@1)",
    )
    openclaw_parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed for the test run (default: 0)",
    )
    openclaw_parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        metavar="SECONDS",
        help="Wall-clock timeout for the test run",
    )
    openclaw_parser.add_argument(
        "--gateway",
        action="store_true",
        help="Also scaffold a gateway-wired adapter (requires running OpenClaw gateway)",
    )
    openclaw_parser.set_defaults(func=_cmd_openclaw)

    openclaw_export_parser = subparsers.add_parser(
        "openclaw-export",
        help="Export a certified TraceCore bundle for a tested OpenClaw adapter",
    )
    openclaw_export_parser.add_argument(
        "--agent-id",
        dest="agent_id",
        metavar="ID",
        help="OpenClaw agent ID (auto-detected if only one agent exists)",
    )
    openclaw_export_parser.add_argument(
        "--out-dir",
        dest="out_dir",
        default="tracecore_export",
        metavar="DIR",
        help="Output directory for the bundle (default: tracecore_export/)",
    )
    openclaw_export_parser.set_defaults(func=_cmd_openclaw_export)

    args, unknown = parser.parse_known_args()
    if unknown and getattr(args, "command", None) == "maintain":
        setattr(args, "_passthrough", unknown)

    config = _load_config_from_args(getattr(args, "config", None))
    setattr(args, "_config", config)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
